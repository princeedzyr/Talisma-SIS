import re
from uuid import uuid4

from wingman_ai.business_skills.record_creation.capability import RecordCreationCapability, build_actions as build_create_actions
from wingman_ai.business_skills.record_creation.service import extract_create_data, primary_name_field
from wingman_ai.capabilities.base import CapabilityResult
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.repositories.conversation_repository import clear_pending_workflow_session, set_pending_workflow_session
from wingman_ai.workflow_engine.registry import get_runtime_workflow_registry


OPPORTUNITY_PARTY_DOCTYPES = ("Customer", "Lead", "Prospect")
OPPORTUNITY_SEARCH_DOCTYPES = OPPORTUNITY_PARTY_DOCTYPES
PARTY_DECISION_PREFIX = "create opportunity party "
FAST_PARTY_SEARCH_FIELDS = {
    "Customer": ("name", "customer_name"),
    "Lead": ("name", "lead_name", "company_name", "organization_name", "title"),
    "Prospect": ("name", "company_name", "prospect_name"),
    "Opportunity": ("name", "title", "party_name"),
}


class BusinessWorkflowService:
    """Coordinates business goals while delegating Talisma OneCampus operations to existing skills."""

    def __init__(self, creation_capability=None):
        self.creation_capability = creation_capability or RecordCreationCapability()

    def handle_goal(self, message, context=None, intent=None):
        context = context or {}
        pending_workflow = context.get("pending_workflow_session")
        if pending_workflow and is_cancel_workflow_message(message):
            return self.cancel_workflow(pending_workflow, context=context)
        if pending_workflow and is_party_decision_message(message):
            return self.prepare_missing_party_creation(message, pending_workflow, context=context, intent=intent)
        if pending_workflow and is_start_workflow_message(message):
            return self.start_workflow(pending_workflow, context=context, intent=intent)

        goal_doctype = detect_goal_doctype(intent, message)
        if goal_doctype == "Opportunity":
            return self.handle_opportunity_goal(message, context=context, intent=intent)

        create_result = self.simulate_goal(message=message, context=context, intent=intent)
        if create_result.get("doctype") == "Opportunity":
            return self.handle_opportunity_goal(message, context=context, intent=intent, create_result=create_result)
        workflow_session = self.build_workflow_session(
            message=message,
            context=context,
            intent=intent,
            create_result=create_result,
        )
        workflow_session["status"] = "preview_ready"
        workflow_session["workflow_id"] = uuid4().hex
        self.persist_workflow_session(workflow_session, create_result=create_result, context=context)
        return CapabilityResult(
            message=format_workflow_preview(workflow_session),
            actions=build_preview_actions(workflow_session),
            data={
                "executed_capability": "business_workflow",
                "business_skill": "business_workflow",
                "operation": "create",
                "result": create_result,
                "business_workflow": workflow_session,
                "workflow_session": workflow_session,
                "workflow_delegated_to": None,
            },
            requires_confirmation=False,
        )

    def handle_opportunity_goal(self, message, context=None, intent=None, create_result=None):
        context = context or {}
        create_result = create_result or self.build_lightweight_opportunity_goal(message, context=context, intent=intent)
        opportunity_data = dict(create_result.get("data") or {})
        entity = opportunity_party_query(message, opportunity_data)
        workflow_session = self.build_workflow_session(
            message=message,
            context=context,
            intent=intent,
            create_result=create_result,
        )
        workflow_session["workflow_id"] = uuid4().hex
        workflow_session["opportunity_data"] = opportunity_data
        workflow_session["entity"] = entity

        if not entity:
            workflow_session["status"] = "collecting_inputs"
            self.persist_workflow_session(workflow_session, create_result=create_result, context=context)
            return CapabilityResult(
                message=create_result.get("message") or format_workflow_preview(workflow_session),
                actions=build_create_actions(create_result),
                data=workflow_result_payload(create_result, workflow_session, delegated_to="record_creation"),
                requires_confirmation=any(action.get("requires_confirmation") for action in build_create_actions(create_result)),
            )

        context_issue = opportunity_non_party_context(entity)
        if context_issue:
            fieldname = context_issue.get("fieldname")
            if fieldname:
                opportunity_data.setdefault(fieldname, context_issue.get("value"))
                workflow_session["opportunity_data"] = opportunity_data
            workflow_session["status"] = "collecting_party"
            workflow_session["party_resolution"] = {"status": "needs_party", **context_issue}
            self.persist_workflow_session(workflow_session, create_result=create_result, context=context)
            return CapabilityResult(
                message=format_opportunity_party_context_question(context_issue),
                actions=[],
                data=workflow_result_payload(create_result, workflow_session),
                requires_confirmation=False,
            )

        party_resolution = self.resolve_opportunity_party(entity, user=context.get("user"))
        workflow_session["party_resolution"] = party_resolution
        if party_resolution.get("status") == "found":
            opportunity_data["opportunity_from"] = party_resolution.get("doctype")
            opportunity_data["party_name"] = party_resolution.get("name")
            prepared = self.prepare_opportunity_review(opportunity_data, context=context, intent=intent)
            workflow_session = self.build_workflow_session(message=message, context=context, intent=intent, create_result=prepared)
            workflow_session["workflow_id"] = workflow_session.get("workflow_id") or uuid4().hex
            workflow_session["status"] = "awaiting_confirmation" if prepared.get("ready") else workflow_status(prepared)
            workflow_session["opportunity_data"] = prepared.get("data") or opportunity_data
            workflow_session["entity"] = entity
            workflow_session["party_resolution"] = party_resolution
            self.persist_workflow_session(workflow_session, create_result=prepared, context=context)
            actions = self.opportunity_create_actions(prepared, workflow_session, context=context)
            return CapabilityResult(
                message=prepared.get("message") or "Opportunity review is ready.",
                actions=actions,
                data=workflow_result_payload(prepared, workflow_session),
                requires_confirmation=any(action.get("requires_confirmation") for action in actions),
            )

        workflow_session["status"] = "awaiting_party_decision"
        self.persist_workflow_session(workflow_session, create_result=create_result, context=context)
        return CapabilityResult(
            message=format_missing_party_question(entity, party_resolution),
            actions=build_missing_party_actions(entity, workflow_session),
            data=workflow_result_payload(create_result, workflow_session),
            requires_confirmation=False,
        )

    def build_lightweight_opportunity_goal(self, message, context=None, intent=None):
        creation_service = self.creation_capability.service
        blueprint = creation_service.build_blueprint("Opportunity")
        fields = blueprint["fields"]["all"]
        data = extract_create_data(message, "Opportunity", fields, intent=intent, blueprint=blueprint)
        data, defaults_applied = creation_service.apply_defaults(
            "Opportunity",
            data,
            fields,
            context=context,
            user=(context or {}).get("user"),
            blueprint=blueprint,
        )
        return {
            "operation": "create",
            "supported": True,
            "doctype": "Opportunity",
            "blueprint": blueprint,
            "data": data,
            "defaults_applied": defaults_applied,
            "missing_fields": [],
            "missing_dependencies": [],
            "validation_issues": [],
            "preflight": {"valid": True, "issues": []},
            "ready": False,
        }

    def simulate_goal(self, message, context=None, intent=None):
        creation_service = self.creation_capability.service
        doctype = creation_service.resolve_create_doctype(message, intent=intent)
        if not doctype:
            return {
                "operation": "create",
                "supported": False,
                "ready": False,
                "doctype": detect_goal_doctype(intent, message) or "Record",
                "message": "I could not identify a supported Talisma OneCampus record type for this workflow.",
            }
        blueprint = creation_service.build_blueprint(doctype)
        fields = blueprint["fields"]["all"]
        data = extract_create_data(message, doctype, fields, intent=intent, blueprint=blueprint)
        return creation_service.build_prepared_create(
            doctype,
            data,
            fields,
            context=context,
            user=(context or {}).get("user"),
            intent=intent,
            blueprint=blueprint,
        )

    def persist_workflow_session(self, workflow_session, create_result=None, context=None):
        context = context or {}
        conversation_id = context.get("conversation_id")
        if not conversation_id:
            return None
        return set_pending_workflow_session(
            conversation_id,
            {
                "workflow_id": workflow_session.get("workflow_id"),
                "original_message": workflow_session.get("business_goal"),
                "workflow_session": workflow_session,
                "simulation": create_result or {},
                "operation": "create",
                "doctype": (workflow_session.get("primary_goal") or {}).get("doctype"),
            },
            user=context.get("user"),
        )

    def start_workflow(self, pending_workflow, context=None, intent=None):
        context = dict(context or {})
        original_message = pending_workflow.get("original_message") or ""
        clear_pending_workflow_session(context.get("conversation_id"), user=context.get("user"))
        context.pop("pending_workflow_session", None)
        context.setdefault("raw", {})["message"] = original_message
        delegated = self.creation_capability.handle(message=original_message, context=context, intent=intent)
        create_result = (delegated.data or {}).get("result") or {}
        workflow_session = self.build_workflow_session(
            message=original_message,
            context=context,
            intent=intent,
            create_result=create_result,
        )
        workflow_session["status"] = "execution_started"
        workflow_session["workflow_id"] = pending_workflow.get("workflow_id")
        delegated.message = format_workflow_started_message(workflow_session, delegated.message)
        data = dict(delegated.data or {})
        data["executed_capability"] = "business_workflow"
        data["business_workflow"] = workflow_session
        data["workflow_session"] = workflow_session
        data["workflow_delegated_to"] = "record_creation"
        delegated.data = data
        return delegated

    def prepare_missing_party_creation(self, message, pending_workflow, context=None, intent=None):
        context = context or {}
        workflow_session = pending_workflow.get("workflow_session") or pending_workflow or {}
        target_doctype = selected_party_doctype(message)
        entity = workflow_session.get("entity")
        if target_doctype not in OPPORTUNITY_PARTY_DOCTYPES or not entity:
            return CapabilityResult(
                message="Please choose Create Customer, Create Lead, or Create Prospect to continue this Opportunity workflow.",
                actions=build_missing_party_actions(entity or "this organization", workflow_session),
                data=workflow_result_payload({}, workflow_session),
                requires_confirmation=False,
            )

        creation_service = self.creation_capability.service
        blueprint = creation_service.build_blueprint(target_doctype)
        fields = blueprint["fields"]["all"]
        data = dependency_create_data(target_doctype, entity, fields, blueprint)
        prepared = creation_service.build_prepared_create(target_doctype, data, fields, context=context, user=context.get("user"), intent=None, blueprint=blueprint)
        resume_action = build_resume_after_dependency_action(workflow_session, target_doctype, entity, context=context)
        prepared["resume_action"] = resume_action
        creation_service.sync_pending_draft(prepared, context=context)
        actions = attach_resume_action(build_create_actions(prepared), resume_action)
        return CapabilityResult(
            message=prepared.get("message") or f"{target_doctype} review is ready.",
            actions=actions,
            data=workflow_result_payload(prepared, {**workflow_session, "status": "creating_dependency", "dependency_doctype": target_doctype}, delegated_to="record_creation"),
            requires_confirmation=any(action.get("requires_confirmation") for action in actions),
        )

    def resume_after_dependency(self, workflow_id=None, dependency_doctype=None, entity=None, opportunity_data=None, business_goal=None, conversation_id=None, user=None):
        opportunity_data = dict(opportunity_data or {})
        dependency = self.find_party_record(dependency_doctype, entity, user=user) if dependency_doctype else None
        party_name = (dependency or {}).get("name") or entity
        if dependency_doctype and party_name:
            opportunity_data["opportunity_from"] = dependency_doctype
            opportunity_data["party_name"] = party_name
        prepared = self.prepare_opportunity_review(opportunity_data, context={"user": user, "conversation_id": conversation_id}, intent=None)
        workflow_session = self.build_workflow_session(message=business_goal or f"Create Opportunity for {entity}", context={"user": user}, intent=None, create_result=prepared)
        workflow_session["workflow_id"] = workflow_id or uuid4().hex
        workflow_session["status"] = "awaiting_confirmation" if prepared.get("ready") else workflow_status(prepared)
        workflow_session["opportunity_data"] = prepared.get("data") or opportunity_data
        workflow_session["entity"] = entity
        workflow_session["party_resolution"] = {"status": "found", "doctype": dependency_doctype, "name": party_name}
        if conversation_id:
            set_pending_workflow_session(
                conversation_id,
                {
                    "workflow_id": workflow_session.get("workflow_id"),
                    "original_message": business_goal,
                    "workflow_session": workflow_session,
                    "simulation": prepared,
                    "operation": "create",
                    "doctype": "Opportunity",
                },
                user=user,
            )
        return {
            "success": True,
            "message": "Resumed Opportunity workflow.",
            "result": prepared,
            "follow_up": {
                "message": prepared.get("message") or "Opportunity review is ready.",
                "actions": self.opportunity_create_actions(prepared, workflow_session, context={"conversation_id": conversation_id, "user": user}),
                "workflow": {"type": "business_workflow", "doctype": "Opportunity", "remaining_steps": 0},
            },
        }

    def complete_opportunity_goal(self, workflow_id=None, business_goal=None, opportunity_data=None, conversation_id=None, user=None):
        opportunity_data = dict(opportunity_data or {})
        found = self.find_created_opportunity(opportunity_data, user=user)
        if conversation_id:
            clear_pending_workflow_session(conversation_id, user=user)
        return {
            "success": True,
            "message": "Opportunity workflow completed.",
            "follow_up": {
                "message": format_opportunity_outcome(business_goal, opportunity_data, found),
                "actions": build_opportunity_outcome_actions(found),
                "workflow": {"type": "business_workflow", "doctype": "Opportunity", "workflow_id": workflow_id, "remaining_steps": 0},
            },
        }

    def prepare_opportunity_review(self, data, context=None, intent=None):
        creation_service = self.creation_capability.service
        blueprint = creation_service.build_blueprint("Opportunity")
        fields = blueprint["fields"]["all"]
        return creation_service.build_prepared_create("Opportunity", data, fields, context=context, user=(context or {}).get("user"), intent=intent, blueprint=blueprint)

    def resolve_opportunity_party(self, entity, user=None):
        matches = []
        for doctype in OPPORTUNITY_SEARCH_DOCTYPES:
            match = self.find_party_record(doctype, entity, user=user)
            if match:
                item = {"doctype": doctype, **match}
                matches.append(item)
        for doctype in OPPORTUNITY_PARTY_DOCTYPES:
            match = next((item for item in matches if item.get("doctype") == doctype), None)
            if match:
                return {
                    "status": "found",
                    "doctype": doctype,
                    "name": match.get("name"),
                    "label": match.get("label") or match.get("name"),
                    "matches": matches,
                }
        return {"status": "missing", "entity": entity, "matches": matches, "searched_doctypes": list(OPPORTUNITY_SEARCH_DOCTYPES)}

    def find_party_record(self, doctype, entity, user=None):
        if not doctype or not entity:
            return None
        fast_match = self.fast_party_record_search(doctype, entity, user=user)
        if fast_match:
            return fast_match

        return None

    def fast_party_record_search(self, doctype, entity, user=None):
        fields = fast_party_search_fields(doctype)
        if not fields:
            return None
        erp_service = self.creation_capability.service.erp_service
        if not hasattr(erp_service, "list_documents"):
            return None

        for fieldname in fields:
            if not fieldname:
                continue
            response = erp_service.list_documents(
                doctype,
                fields=fields,
                filters={fieldname: entity},
                page=1,
                page_size=1,
                user=user,
            )
            if not response or not response.get("success"):
                continue
            rows = ((response.get("result") or {}).get("rows") or [])
            exact = first_exact_party_match(normalize_erp_search_rows(rows), entity)
            if exact:
                return {"name": exact.get("value") or exact.get("label"), "label": exact.get("label"), "description": exact.get("description")}
        return None

    def find_created_opportunity(self, data, user=None):
        title = (data or {}).get("title") or (data or {}).get("party_name")
        if not title:
            return None
        return self.find_party_record("Opportunity", title, user=user)

    def opportunity_create_actions(self, prepared, workflow_session, context=None):
        actions = build_create_actions(prepared)
        completion_action = build_complete_opportunity_action(workflow_session, prepared, context=context)
        return attach_resume_action(actions, completion_action)

    def cancel_workflow(self, pending_workflow, context=None):
        context = context or {}
        clear_pending_workflow_session(context.get("conversation_id"), user=context.get("user"))
        doctype = pending_workflow.get("doctype") or ((pending_workflow.get("workflow_session") or {}).get("primary_goal") or {}).get("doctype") or "record"
        return CapabilityResult(
            message=f"Workflow cancelled. No Talisma OneCampus {doctype} data was changed.",
            actions=[],
            data={
                "executed_capability": "business_workflow",
                "business_skill": "business_workflow",
                "operation": "create",
                "cancelled": True,
                "business_workflow": pending_workflow.get("workflow_session") or {},
            },
            requires_confirmation=False,
        )

    def build_workflow_session(self, message, context=None, intent=None, create_result=None):
        create_result = create_result or {}
        doctype = create_result.get("doctype") or detect_goal_doctype(intent, message) or "Record"
        blueprint = create_result.get("blueprint") or {}
        metadata_plan = build_metadata_plan(doctype, blueprint)
        graph = build_execution_graph(message, doctype, create_result, metadata_plan)
        sequence = graph["nodes"]
        dependencies = build_dependency_plan(create_result, metadata_plan)

        return {
            "type": "business_workflow",
            "status": workflow_status(create_result),
            "business_goal": str(message or "").strip(),
            "primary_goal": {
                "operation": "create",
                "doctype": doctype,
                "summary": f"Create {doctype}",
            },
            "secondary_goals": infer_secondary_goals(message, create_result),
            "target_modules": infer_target_modules(doctype, context=context, blueprint=blueprint),
            "metadata_discovery": build_metadata_discovery(blueprint),
            "required_doctypes": metadata_plan["required_doctypes"],
            "dependencies": dependencies,
            "missing_information": create_result.get("missing_fields") or [],
            "validation": {
                "preflight_status": "passed" if (create_result.get("preflight") or {}).get("valid", True) else "needs_attention",
                "issues": create_result.get("validation_issues") or [],
            },
            "execution_graph": graph,
            "workflow_graph": graph,
            "execution_sequence": sequence,
            "current_step": current_step(sequence),
            "completed_steps": [item for item in sequence if item.get("status") == "completed"],
            "pending_steps": [item for item in sequence if item.get("status") == "pending"],
            "review_state": "ready" if create_result.get("ready") else "collecting_inputs",
            "retry_state": "preserved_by_create_session" if not create_result.get("ready") else "not_required",
            "delegated_operation": {
                "skill": "record_creation",
                "operation": "create",
                "doctype": doctype,
                "ready": bool(create_result.get("ready")),
            },
            "next_best_actions": next_best_actions(doctype, blueprint),
        }


def build_metadata_plan(doctype, blueprint):
    fields = (blueprint or {}).get("fields") or {}
    editable = fields.get("editable") or []
    required = fields.get("required") or []
    conditional_required = fields.get("conditional_required") or []
    required_links = []
    optional_links = []
    for link in (blueprint or {}).get("links") or []:
        if link.get("required"):
            required_links.append(link)
        else:
            optional_links.append(link)

    required_doctypes = [doctype]
    for link in required_links + optional_links:
        target = link.get("target_doctype") or link.get("dynamic_target_field")
        if target and target not in required_doctypes:
            required_doctypes.append(target)

    return {
        "doctype": doctype,
        "editable_fields": [field.get("fieldname") for field in editable if field.get("fieldname")],
        "required_fields": [field.get("fieldname") for field in required if field.get("fieldname")],
        "conditional_required_fields": [field.get("fieldname") for field in conditional_required if field.get("fieldname")],
        "field_details": [field_detail(field, fields, blueprint) for field in editable if should_graph_field(field, fields)],
        "required_links": required_links,
        "optional_links": optional_links,
        "required_doctypes": required_doctypes,
    }


def field_detail(field, fields, blueprint):
    fieldname = field.get("fieldname")
    default_values = (blueprint or {}).get("default_values") or {}
    return {
        "fieldname": fieldname,
        "label": field_label(field),
        "fieldtype": field.get("fieldtype"),
        "options": field.get("options"),
        "mandatory": field in (fields.get("required") or []),
        "conditionally_mandatory": field in (fields.get("conditional_required") or []),
        "link": field.get("fieldtype") in {"Link", "Dynamic Link"},
        "has_default": fieldname in default_values or field.get("default") not in (None, ""),
        "default_value": default_values.get(fieldname, field.get("default")),
        "depends_on": field.get("depends_on"),
        "mandatory_depends_on": field.get("mandatory_depends_on"),
        "fetch_from": field.get("fetch_from"),
    }


def should_graph_field(field, fields):
    if not is_editable_business_field(field):
        return False
    if field in (fields.get("required") or []) or field in (fields.get("conditional_required") or []):
        return True
    if field.get("fieldtype") in {"Link", "Dynamic Link"}:
        return True
    return field.get("fieldname") in {"title", "subject"} or field.get("fieldtype") in {"Currency", "Float", "Percent", "Date"}


def build_metadata_discovery(blueprint):
    metadata = (blueprint or {}).get("metadata") or {}
    fields = (blueprint or {}).get("fields") or {}
    return {
        "doctype_loaded": bool((blueprint or {}).get("doctype")),
        "field_count": len(fields.get("all") or []),
        "editable_field_count": len(fields.get("editable") or []),
        "required_field_count": len(fields.get("required") or []),
        "conditional_required_field_count": len(fields.get("conditional_required") or []),
        "link_field_count": len(fields.get("links") or []),
        "child_table_count": len(fields.get("child_tables") or []),
        "property_setters": len((blueprint or {}).get("property_setters") or []),
        "custom_fields": len((blueprint or {}).get("custom_fields") or []),
        "workflows": len((blueprint or {}).get("workflow_rules") or []),
        "permissions": len((blueprint or {}).get("permission_rules") or []),
        "server_scripts": len(metadata.get("server_scripts") or []),
        "client_scripts": len(metadata.get("client_scripts") or []),
        "naming": (blueprint or {}).get("naming") or {},
        "validation_metadata": (blueprint or {}).get("validation_metadata") or {},
    }


def build_dependency_plan(create_result, metadata_plan):
    dependencies = []
    for item in create_result.get("missing_dependencies") or []:
        dependencies.append(
            {
                "status": "missing",
                "fieldname": item.get("fieldname"),
                "target_doctype": item.get("target_doctype"),
                "value": item.get("value"),
                "recovery": "use_existing_dependency_resolution",
            }
        )

    known = {item.get("fieldname") for item in dependencies}
    for link in metadata_plan.get("required_links") or []:
        if link.get("fieldname") not in known:
            dependencies.append(
                {
                    "status": "managed_by_validation",
                    "fieldname": link.get("fieldname"),
                    "target_doctype": link.get("target_doctype") or link.get("dynamic_target_field"),
                    "value": None,
                    "recovery": "metadata_driven_follow_up",
                }
            )
    return dependencies


def build_execution_graph(message, doctype, create_result, metadata_plan):
    data = create_result.get("data") or {}
    nodes = [
        graph_node("goal", "User Goal", "business_goal", "completed", value=str(message or "").strip()),
        graph_node("target", f"Target {doctype}", "doctype", "completed", doctype=doctype),
        graph_node("metadata", "Discover Talisma OneCampus metadata", "metadata_discovery", "completed"),
    ]

    dependency_by_field = {
        item.get("fieldname"): item
        for item in create_result.get("missing_dependencies") or []
        if item.get("fieldname")
    }
    next_fieldname = ((create_result.get("next_missing_field") or {}).get("fieldname"))
    missing_labels = set(create_result.get("missing_fields") or [])
    missing_fieldnames = {
        field.get("fieldname")
        for field in (create_result.get("blueprint") or {}).get("fields", {}).get("all", [])
        if field_label(field) in missing_labels
    }

    for item in metadata_plan.get("field_details") or []:
        status = field_node_status(item, data, dependency_by_field, next_fieldname, missing_fieldnames)
        nodes.append(
            graph_node(
                f"field:{item.get('fieldname')}",
                item.get("label"),
                "field",
                status,
                fieldname=item.get("fieldname"),
                fieldtype=item.get("fieldtype"),
                mandatory=item.get("mandatory"),
                conditionally_mandatory=item.get("conditionally_mandatory"),
                has_default=item.get("has_default"),
                can_derive=bool(data.get(item.get("fieldname")) or item.get("has_default") or item.get("fetch_from")),
                needs_user_input=status == "current",
                requires_dependency=item.get("link"),
                target_doctype=item.get("options") if item.get("fieldtype") == "Link" else None,
                dynamic_target_field=item.get("options") if item.get("fieldtype") == "Dynamic Link" else None,
                value=data.get(item.get("fieldname")),
                default_value=item.get("default_value"),
                depends_on=item.get("depends_on"),
                mandatory_depends_on=item.get("mandatory_depends_on"),
                fetch_from=item.get("fetch_from"),
                permission_scope="Talisma OneCampus permissions apply at execution",
            )
        )

    for dependency in build_dependency_plan(create_result, metadata_plan):
        nodes.append(
            graph_node(
                f"dependency:{dependency.get('fieldname') or dependency.get('target_doctype')}",
                f"Resolve {dependency.get('target_doctype') or 'Linked Record'}",
                "dependency",
                "current" if dependency.get("status") == "missing" else "pending",
                fieldname=dependency.get("fieldname"),
                target_doctype=dependency.get("target_doctype"),
                value=dependency.get("value"),
                recovery=dependency.get("recovery"),
            )
        )

    has_missing_fields = bool(create_result.get("next_missing_field") or create_result.get("missing_fields"))
    has_dependencies = bool(create_result.get("missing_dependencies") or create_result.get("missing_link_dependencies"))
    ready = bool(create_result.get("ready"))
    nodes.extend(
        [
            graph_node("validation", "Validate using Talisma OneCampus rules", "validation", "completed" if ready else ("pending" if has_missing_fields or has_dependencies else "current")),
            graph_node("review", "Show Talisma OneCampus review before write", "review", "current" if ready else "pending"),
            graph_node("execute", "Execute only after confirmation", "execution", "pending"),
            graph_node("verify", "Reload and verify created record", "verification", "pending"),
        ]
    )
    return {"nodes": nodes, "edges": build_graph_edges(nodes), "mode": "runtime_metadata_planning"}


def graph_node(node_id, label, node_type, status, **extra):
    payload = {"id": node_id, "label": label, "type": node_type, "status": status}
    payload.update(extra)
    return payload


def field_node_status(item, data, dependency_by_field, next_fieldname, missing_fieldnames):
    fieldname = item.get("fieldname")
    if fieldname in dependency_by_field:
        return "blocked"
    if fieldname == next_fieldname:
        return "current"
    if fieldname in data and data.get(fieldname) not in (None, "", []):
        return "completed"
    if fieldname in missing_fieldnames:
        return "current"
    if item.get("mandatory") or item.get("conditionally_mandatory"):
        return "pending"
    return "available"


def build_graph_edges(nodes):
    edges = []
    previous = None
    for node in nodes:
        if previous:
            edges.append({"from": previous.get("id"), "to": node.get("id")})
        previous = node
    return edges


def build_execution_sequence(create_result, metadata_plan):
    has_missing_fields = bool(create_result.get("next_missing_field") or create_result.get("missing_fields"))
    has_dependencies = bool(create_result.get("missing_dependencies") or create_result.get("missing_link_dependencies"))
    ready = bool(create_result.get("ready"))

    sequence = [
        step("metadata_discovery", "Discover Talisma OneCampus metadata", "completed"),
        step("workflow_planning", "Plan required CRM operation", "completed"),
        step("collect_inputs", "Collect only missing business details", "current" if has_missing_fields else "completed"),
        step("dependency_resolution", "Resolve linked records", "current" if has_dependencies else ("completed" if not has_missing_fields else "pending")),
        step("preflight_validation", "Validate using Talisma OneCampus rules", "completed" if ready else "pending"),
        step("review", "Review before creating Talisma OneCampus data", "current" if ready else "pending"),
        step("execute", "Create the record through Talisma OneCampus APIs", "pending"),
        step("verify", "Verify the business outcome", "pending"),
    ]
    return sequence


def step(step_id, label, status):
    return {"id": step_id, "label": label, "status": status}


def current_step(sequence):
    return next((item for item in sequence if item.get("status") == "current"), None)


def workflow_status(create_result):
    if create_result.get("ready"):
        return "awaiting_confirmation"
    if create_result.get("missing_dependencies") or create_result.get("missing_link_dependencies"):
        return "resolving_dependencies"
    if create_result.get("next_missing_field") or create_result.get("missing_fields"):
        return "collecting_inputs"
    return "planning"


def is_start_workflow_message(message):
    text = normalize_control_message(message)
    return text == "start" or text.startswith("start workflow") or text.startswith("begin workflow")


def is_cancel_workflow_message(message):
    text = normalize_control_message(message)
    return text in {"cancel", "cancel workflow", "stop workflow", "abort workflow", "never mind", "nevermind"}


def normalize_control_message(message):
    return " ".join(str(message or "").strip().lower().split())


def infer_secondary_goals(message, create_result):
    text = str(message or "").lower()
    goals = []
    if any(token in text for token in ("worth", "value", "amount", "budget")):
        goals.append("Capture commercial value")
    if any(token in text for token in ("assign", "owner", "sales person", "salesperson")):
        goals.append("Capture responsible owner where Talisma OneCampus exposes an editable field")
    if create_result.get("missing_dependencies"):
        goals.append("Resolve linked CRM records")
    return goals


def infer_target_modules(doctype, context=None, blueprint=None):
    workspace = ((context or {}).get("object") or {}).get("workspace")
    metadata = (blueprint or {}).get("metadata") or {}
    module = metadata.get("module")
    modules = []
    if workspace:
        modules.append(workspace)
    if module:
        modules.append(module)
    modules.append("Talisma OneCampus")
    return list(dict.fromkeys(modules))


def next_best_actions(doctype, blueprint=None):
    recommendations = (blueprint or {}).get("post_creation_recommendations") or []
    if recommendations:
        return recommendations[:5]
    return [
        f"Open {doctype}",
        f"Review related {doctype} activity",
        "Create the next linked Talisma OneCampus document when the business step requires it",
    ]


def detect_goal_doctype(intent, message):
    return get_runtime_workflow_registry().resolve_doctype(message=message, intent=intent, operation="create")


def workflow_result_payload(create_result, workflow_session, delegated_to=None):
    return {
        "executed_capability": "business_workflow",
        "business_skill": "business_workflow",
        "operation": "create",
        "result": create_result,
        "business_workflow": workflow_session,
        "workflow_session": workflow_session,
        "workflow_delegated_to": delegated_to,
    }


def opportunity_party_query(message, data=None):
    data = data or {}
    for fieldname in ("party_name", "customer", "lead", "prospect", "title"):
        value = data.get(fieldname)
        if value not in (None, "", []):
            return clean_business_text(value)
    text = str(message or "")
    match = re.search(r"\bopportunit(?:y|ies)\s+(?:for|with)\s+([A-Za-z0-9][A-Za-z0-9 .&_-]{1,120})", text, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(?:for|with)\s+([A-Za-z0-9][A-Za-z0-9 .&_-]{1,120})", text, re.IGNORECASE)
    if not match:
        return None
    return clean_business_text(match.group(1))


def opportunity_non_party_context(entity):
    text = clean_business_text(entity)
    match = re.match(r"^(territory|region|location|area|city|state|country)\s+(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    qualifier = match.group(1).lower()
    value = clean_business_text(match.group(2))
    if not value:
        return None
    field_map = {
        "territory": "territory",
        "region": "territory",
        "location": "territory",
        "area": "territory",
        "city": "city",
        "state": "state",
        "country": "country",
    }
    return {
        "qualifier": qualifier,
        "label": qualifier.title(),
        "value": value,
        "fieldname": field_map.get(qualifier),
    }

def clean_business_text(value):
    text = str(value or "")
    text = re.split(
        r"\b(?:worth|valued|value|amount|budget|assign|assigned|owner|salesperson|sales person|with email|email|phone|mobile)\b",
        text,
        flags=re.IGNORECASE,
    )[0]
    return " ".join(text.strip().strip(".,;:()[]{}\"'").split())


def first_exact_party_match(rows, query):
    normalized = normalize_match_key(query)
    if not normalized:
        return None
    for row in rows or []:
        values = [row.get("label"), row.get("value"), row.get("description")] + list(row.get("aliases") or [])
        if any(normalize_match_key(value) == normalized for value in values if value):
            return row
    return None


def fast_party_search_fields(doctype):
    return list(FAST_PARTY_SEARCH_FIELDS.get(doctype) or ("name",))


def normalize_erp_search_rows(rows):
    normalized = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        aliases = []
        for fieldname, value in row.items():
            if fieldname == "name" or value in (None, "", []):
                continue
            aliases.append(value)
        normalized.append(
            {
                "value": name or next((value for value in aliases if value), None),
                "label": next((value for value in aliases if value), None) or name,
                "description": name,
                "aliases": aliases,
            }
        )
    return normalized


def normalize_match_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def selected_party_doctype(message):
    text = normalize_control_message(message)
    if text.startswith(PARTY_DECISION_PREFIX):
        text = text[len(PARTY_DECISION_PREFIX) :].strip()
    for doctype in OPPORTUNITY_PARTY_DOCTYPES:
        if normalize_control_message(doctype) in text:
            return doctype
    return None


def is_party_decision_message(message):
    return selected_party_doctype(message) is not None and normalize_control_message(message).startswith(PARTY_DECISION_PREFIX)


def format_missing_party_question(entity, party_resolution=None):
    return "\n".join(
        [
            "Opportunity Party Required",
            "",
            f"I couldn't find {entity}. How would you like to continue?",
            "",
            "Current Status",
            "- I have not changed Talisma OneCampus data yet.",
            "- I will create the selected CRM party first, then resume this Opportunity automatically.",
        ]
    )


def format_opportunity_party_context_question(context_issue):
    label = context_issue.get("label") or "Context"
    value = context_issue.get("value") or "the provided value"
    return "\n".join(
        [
            "Opportunity Party Required",
            "",
            "Opportunity needs a Customer, Lead, or Prospect before it can be created.",
            f"I captured {label}: {value}.",
            "",
            "Next Detail",
            "- Tell me the Customer, Lead, or Prospect for this Opportunity.",
            "",
            "Example",
            f"- Create opportunity for ABC Technologies in {label.lower()} {value}.",
        ]
    )

def build_missing_party_actions(entity, workflow_session):
    workflow_id = workflow_session.get("workflow_id") or ""
    actions = []
    for doctype in OPPORTUNITY_PARTY_DOCTYPES:
        actions.append(
            {
                "type": "send_message",
                "label": f"Create {doctype}",
                "payload": {"message": f"{PARTY_DECISION_PREFIX}{doctype} {workflow_id}".strip()},
                "requires_confirmation": False,
                "auto_execute": False,
                "enabled": True,
                "loading_type": "card",
            }
        )
    actions.append(
        {
            "type": "send_message",
            "label": "Cancel",
            "payload": {"message": f"cancel workflow {workflow_id}".strip()},
            "requires_confirmation": False,
            "auto_execute": False,
            "enabled": True,
            "loading_type": "inline",
        }
    )
    return actions


def dependency_create_data(doctype, entity, fields, blueprint):
    fieldname = primary_name_field(doctype, fields, blueprint=blueprint)
    if not fieldname:
        return {}
    return {fieldname: entity}


def build_resume_after_dependency_action(workflow_session, dependency_doctype, entity, context=None):
    return {
        "type": "business_workflow_resume",
        "label": "Continue Opportunity",
        "method": "wingman_ai.api.business_workflows.resume_after_dependency",
        "payload": {
            "workflow_id": workflow_session.get("workflow_id"),
            "dependency_doctype": dependency_doctype,
            "entity": entity,
            "opportunity_data": workflow_session.get("opportunity_data") or {},
            "business_goal": workflow_session.get("business_goal"),
            "conversation_id": (context or {}).get("conversation_id"),
        },
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def build_complete_opportunity_action(workflow_session, prepared, context=None):
    return {
        "type": "business_workflow_complete",
        "label": "Show Outcome",
        "method": "wingman_ai.api.business_workflows.complete_opportunity_goal",
        "payload": {
            "workflow_id": workflow_session.get("workflow_id"),
            "business_goal": workflow_session.get("business_goal"),
            "opportunity_data": (prepared or {}).get("data") or workflow_session.get("opportunity_data") or {},
            "conversation_id": (context or {}).get("conversation_id"),
        },
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def attach_resume_action(actions, resume_action):
    updated = []
    for action in actions or []:
        item = dict(action)
        if item.get("type") == "create" and item.get("method") == "wingman_ai.api.record_creation.create_record":
            payload = dict(item.get("payload") or {})
            payload["resume_action"] = resume_action
            item["payload"] = payload
        updated.append(item)
    return updated


def format_opportunity_outcome(business_goal, data, found):
    title = (data or {}).get("title") or (found or {}).get("label") or "Opportunity"
    party_type = (data or {}).get("opportunity_from")
    party_name = (data or {}).get("party_name")
    amount = (data or {}).get("opportunity_amount")
    lines = [
        "Opportunity Created",
        "",
        "Outcome",
        f"- Created Opportunity for {title}.",
    ]
    if party_type and party_name:
        lines.append(f"- Linked to {party_type} {party_name}.")
    if amount not in (None, "", []):
        lines.append(f"- Value captured: {format_currency(amount)}.")
    lines.extend(
        [
            "",
            "Verification",
            f"- {'Reloaded the created Opportunity from Talisma OneCampus.' if found else 'Talisma OneCampus accepted the create request; I could not reload it by title from the current permissions.'}",
            "",
            "Next Actions",
            "- Open the Opportunity and review the sales stage.",
            "- Create a follow-up task or quotation when the deal is ready.",
        ]
    )
    return "\n".join(lines)


def build_opportunity_outcome_actions(found):
    docname = (found or {}).get("name")
    return [
        {
            "type": "navigate",
            "label": "Open Opportunity",
            "target": {
                "label": f"Opportunity {docname}" if docname else "Opportunity",
                "kind": "document",
                "route": ["Form", "Opportunity", docname] if docname else ["List", "Opportunity"],
                "doctype": "Opportunity",
                "docname": docname,
                "resolved": bool(docname),
            },
            "requires_confirmation": False,
            "auto_execute": False,
            "enabled": True,
        }
    ]


def format_currency(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        number = int(number)
    return f"${number:,}"


def build_preview_actions(session):
    workflow_id = session.get("workflow_id") or ""
    return [
        {
            "type": "send_message",
            "label": "Start Workflow",
            "payload": {"message": f"start workflow {workflow_id}".strip()},
            "requires_confirmation": False,
            "auto_execute": False,
            "enabled": True,
            "loading_type": "card",
        },
        {
            "type": "send_message",
            "label": "Cancel",
            "payload": {"message": f"cancel workflow {workflow_id}".strip()},
            "requires_confirmation": False,
            "auto_execute": False,
            "enabled": True,
            "loading_type": "inline",
        },
    ]


def format_workflow_preview(session):
    primary = session.get("primary_goal") or {}
    graph = session.get("execution_graph") or {}
    nodes = graph.get("nodes") or []
    workflow_steps = preview_steps(nodes)
    estimated_inputs = estimate_inputs(session)
    estimated_steps = len([node for node in nodes if node.get("type") in {"metadata_discovery", "field", "dependency", "validation", "review", "execution", "verification"}])
    if not estimated_steps:
        estimated_steps = len(workflow_steps)

    lines = [
        "Workflow Preview",
        "",
        "Goal",
        session.get("business_goal") or f"Create {primary.get('doctype') or 'record'}",
        "",
        "Workflow",
    ]
    lines.extend([f"- {step}" for step in workflow_steps])
    lines.extend(
        [
            "",
            "Estimated Inputs",
            str(estimated_inputs),
            "",
            "Estimated Steps",
            str(estimated_steps),
            "",
            "Current Status",
            "- I have not changed Talisma OneCampus data yet.",
            "- I will start only after you confirm.",
        ]
    )
    return "\n".join(lines)


def format_workflow_started_message(session, delegated_message):
    current = session.get("current_step") or {}
    lines = [
        "Workflow Started",
        "",
        "Current Step",
        current.get("label") or "Prepare the next Talisma OneCampus action",
        "",
        delegated_message or "I prepared the next workflow step.",
    ]
    return "\n".join(lines)


def preview_steps(nodes):
    labels = []
    for node in nodes or []:
        node_type = node.get("type")
        if node_type == "business_goal":
            labels.append("Understand business goal")
        elif node_type == "doctype":
            labels.append(f"Confirm target {node.get('doctype') or 'DocType'}")
        elif node_type == "metadata_discovery":
            labels.append("Read Talisma OneCampus metadata")
        elif node_type == "dependency":
            target = node.get("target_doctype") or "linked record"
            labels.append(f"Resolve {target}")
        elif node_type == "field" and node.get("status") in {"current", "pending", "blocked"}:
            labels.append(f"Collect {node.get('label')}")
        elif node_type == "validation":
            labels.append("Validate with Talisma OneCampus")
        elif node_type == "review":
            labels.append("Review before creating")
        elif node_type == "execution":
            labels.append("Create record after confirmation")
        elif node_type == "verification":
            labels.append("Verify Talisma OneCampus record")
    return list(dict.fromkeys(labels))[:9] or ["Plan workflow", "Validate with Talisma OneCampus", "Review", "Create record", "Verify Talisma OneCampus record"]


def estimate_inputs(session):
    missing = set(session.get("missing_information") or [])
    dependencies = [item for item in session.get("dependencies") or [] if item.get("status") == "missing"]
    graph = (session.get("execution_graph") or {}).get("nodes") or []
    current_fields = [
        node
        for node in graph
        if node.get("type") == "field" and node.get("status") in {"current", "blocked"} and node.get("needs_user_input")
    ]
    return len(missing) + len(dependencies) + len(current_fields)


def field_label(field):
    return (field or {}).get("label") or str((field or {}).get("fieldname") or "Field").replace("_", " ").title()
