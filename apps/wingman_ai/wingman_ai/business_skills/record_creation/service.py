import json
import re
from datetime import date

from wingman_ai.business_skills.record_creation.formatter import (
    display_fields,
    format_collection_prompt,
    format_creation_review,
    format_dependency_collection_prompt,
    format_draft_cancelled,
    format_field_retry,
    format_preflight_validation_prompt,
    format_unsupported_create,
)
from wingman_ai.creation_session.service import CreationSessionManager
from wingman_ai.conversation_decision_policy import can_use_metadata_default, confidence_for_source, source_from_reason
from wingman_ai.dependency_resolution.service import DependencyResolutionService
from wingman_ai.erp_service import get_erp_service
from wingman_ai.field_filters import is_editable_business_field, is_system_fieldname
from wingman_ai.intent.registry import ENTITY_ALIASES
from wingman_ai.link_resolution import LINK_SEARCH_METHOD
from wingman_ai.link_resolution import UniversalLinkResolutionEngine
from wingman_ai.operation_engine import UniversalOperationFramework
from wingman_ai.repositories.conversation_repository import clear_pending_create_draft, set_pending_create_draft


SUPPORTED_CREATE_DOCTYPES = {
    "Address",
    "Asset",
    "Brand",
    "Campaign",
    "Company",
    "Contact",
    "Course",
    "Course Enrollment",
    "Customer",
    "Customer Group",
    "Delivery Note",
    "Department",
    "Degree",
    "Employee",
    "Item",
    "Item Group",
    "Issue",
    "Journal Entry",
    "Lead",
    "Lead Source",
    "Opportunity",
    "Payment Entry",
    "Patient",
    "Program",
    "Program Enrollment",
    "Project",
    "Purchase Invoice",
    "Purchase Order",
    "Purchase Receipt",
    "Quotation",
    "Sales Invoice",
    "Sales Order",
    "Sales Person",
    "Student",
    "Student Applicant",
    "Student Attendance",
    "Student Group",
    "Supplier",
    "Task",
    "Talisma Curriculum Version",
    "Talisma Student Group Hold",
    "Talisma Class Section",
    "Academic Term",
    "Academic Year",
    "Assessment Result",
    "Territory",
    "UOM",
    "User",
    "Warehouse",
}

PRIMARY_NAME_FIELDS = {
    "Asset": ("asset_name", "item_code"),
    "Brand": ("brand", "brand_name"),
    "Campaign": ("campaign_name",),
    "Company": ("company_name",),
    "Contact": ("first_name", "full_name"),
    "Course": ("course_name", "course_code"),
    "Customer": ("customer_name",),
    "Customer Group": ("customer_group_name",),
    "Department": ("department_name",),
    "Item": ("item_code", "item_name"),
    "Item Group": ("item_group_name",),
    "Issue": ("subject",),
    "Lead": ("lead_name", "company_name", "title"),
    "Lead Source": ("source_name",),
    "Opportunity": ("title",),
    "Patient": ("patient_name", "first_name"),
    "Program": ("program_name",),
    "Project": ("project_name",),
    "Sales Person": ("sales_person_name",),
    "Student": ("student_name", "first_name"),
    "Student Group": ("student_group_name",),
    "Supplier": ("supplier_name",),
    "Task": ("subject",),
    "Talisma Curriculum Version": ("curriculum_code", "version_label"),
    "Talisma Student Group Hold": ("student_group",),
    "Territory": ("territory_name",),
    "UOM": ("uom_name",),
    "User": ("first_name", "full_name"),
    "Warehouse": ("warehouse_name",),
}

ENTITY_DOCTYPE_OVERRIDES = {
    "Invoice": "Sales Invoice",
    "Payment": "Payment Entry",
}

LINK_DEFAULT_CANDIDATES = {
    "Customer Group": ("All Customer Groups", "Demo Customer Group", "Commercial"),
    "Territory": ("All Territories", "Rest Of The World"),
}

CREATE_WORDS = ("create", "new", "add", "make", "register", "draft")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?")
NUMERIC_FIELDTYPES = ("Int", "Float", "Currency", "Percent")
CONTINUE_WITHOUT_ROLES = {"continue", "continue anyway", "continue without roles", "skip roles", "no roles"}
SKIP_OPTIONAL_SETUP = {"skip", "skip for now", "continue", "continue anyway", "not now"}
STANDARD_DYNAMIC_LINK_TARGETS = {
    ("Opportunity", "opportunity_from"): ("Customer", "Lead", "Prospect"),
}


class RecordCreationService:
    def __init__(self, erp_service=None, dependency_service=None, review_builder=None):
        self.erp_service = erp_service or get_erp_service()
        self.operation_framework = UniversalOperationFramework(erp_service=self.erp_service, review_builder=review_builder)
        self.blueprint_builder = self.operation_framework.blueprint_builder
        self.operation_planner = self.operation_framework.plan_builder
        self.dependency_service = dependency_service or DependencyResolutionService(erp_service=self.erp_service)
        self.review_builder = self.operation_framework.review_builder
        self.creation_session = CreationSessionManager(self.erp_service)
        self.link_resolution = UniversalLinkResolutionEngine(erp_service=self.erp_service)
        self.preflight = self.operation_framework.preflight

    def handle_message(self, message, context=None, intent=None):
        context = context or {}
        pending = context.get("pending_create_draft")
        if pending:
            requested_doctype = resolve_alias_from_create_text(
                normalize(message),
                SUPPORTED_CREATE_DOCTYPES,
            )
            # An explicit new create command always starts a fresh draft, even
            # when it targets the same DocType. Otherwise "create a program …"
            # can be mistaken for the answer to the currently pending field.
            if requested_doctype:
                clear_pending_create_draft(context.get("conversation_id"), user=context.get("user"))
                fresh_context = {**context, "pending_create_draft": None}
                return self.prepare_create_from_message(message, context=fresh_context, intent=intent)
            return self.continue_pending_create(message, context=context, intent=intent)
        return self.prepare_create_from_message(message, context=context, intent=intent)

    def prepare_create_from_message(self, message, context=None, intent=None):
        context = context or {}
        doctype = self.resolve_create_doctype(message, intent=intent)
        if not doctype:
            return {
                "operation": "create",
                "supported": False,
                "ready": False,
                "message": format_unsupported_create(message),
            }

        blueprint = self.build_blueprint(doctype)
        fields = blueprint["fields"]["all"]
        data = extract_create_data(message, doctype, fields, intent=intent, blueprint=blueprint)
        prepared = self.build_prepared_create(doctype, data, fields, context=context, user=context.get("user"), intent=intent, blueprint=blueprint)
        self.sync_pending_draft(prepared, context=context)
        return prepared

    def continue_pending_create(self, message, context=None, intent=None):
        context = context or {}
        pending = context.get("pending_create_draft") or {}
        doctype = pending.get("doctype")

        if is_cancel_message(message):
            clear_pending_create_draft(context.get("conversation_id"), user=context.get("user"))
            return {
                "operation": "create",
                "supported": True,
                "doctype": doctype,
                "ready": False,
                "cancelled": True,
                "message": format_draft_cancelled(doctype),
            }

        blueprint = self.build_blueprint(doctype)
        fields = blueprint["fields"]["all"]
        data = dict(pending.get("data") or {})
        conversation_fields = self.conversation_fields(fields, data, doctype=doctype)
        field_map = {field.get("fieldname"): field for field in conversation_fields if field.get("fieldname")}
        setup_state = dict(pending.get("setup_state") or {})
        missing = self.get_missing_mandatory_fields(data, conversation_fields, blueprint=blueprint)
        pending_field = pending.get("next_field") or {}
        field = (
            pending_field
            if pending_field.get("wingman_setup") or pending_field.get("wingman_recovery")
            else field_map.get(pending_field.get("fieldname")) or (missing[0] if missing else None)
        )
        if not field:
            prepared = self.build_prepared_create(doctype, data, fields, context={**context, "setup_state": setup_state}, user=context.get("user"), intent=intent, blueprint=blueprint)
            if pending.get("resume_action"):
                prepared["resume_action"] = pending.get("resume_action")
            self.sync_pending_draft(prepared, context=context)
            return prepared

        if doctype == "Talisma Curriculum Version" and field.get("fieldname") == "requirements":
            field = {**field, "wingman_setup": "curriculum_requirements"}

        parsed = self.parse_answer_for_field(message, field, user=context.get("user"))
        if not parsed.get("accepted"):
            prepared = self.build_prepared_create(doctype, data, fields, context={**context, "setup_state": setup_state}, user=context.get("user"), intent=intent, blueprint=blueprint)
            if pending.get("resume_action"):
                prepared["resume_action"] = pending.get("resume_action")
            self.sync_pending_draft(prepared, context=context)
            prepared["message"] = format_field_retry(prepared, field, reason=parsed.get("message"))
            return prepared

        if parsed.get("value") not in (None, "", []):
            data[field["fieldname"]] = parsed.get("value")
        elif field.get("fieldname") in data:
            data.pop(field.get("fieldname"), None)
        setup_state.update(parsed.get("setup_state") or {})
        if setup_state.get("recovery_forced_fieldname") == field.get("fieldname") and parsed.get("accepted") and parsed.get("value") not in (None, "", []):
            setup_state.pop("recovery_forced_fieldname", None)
        prepared = self.build_prepared_create(doctype, data, fields, context={**context, "setup_state": setup_state}, user=context.get("user"), intent=intent, blueprint=blueprint)
        if pending.get("resume_action"):
            prepared["resume_action"] = pending.get("resume_action")
        prepared["captured_field"] = {"fieldname": field.get("fieldname"), "label": field_label(field), "value": parsed.get("value")}
        self.sync_pending_draft(prepared, context=context)
        return prepared

    def build_prepared_create(self, doctype, data, fields=None, context=None, user=None, intent=None, blueprint=None):
        context = context or {}
        blueprint = blueprint or self.build_blueprint(doctype)
        fields = fields or blueprint["fields"]["all"]
        setup_state = dict(context.get("setup_state") or {})
        supplied_data = dict(data or {})
        data, defaults_applied = self.apply_defaults(doctype, data, fields, context=context, user=user, blueprint=blueprint)
        conversation_fields = self.conversation_fields(fields, data, doctype=doctype)
        missing_fields = self.get_missing_mandatory_fields(data, conversation_fields, blueprint=blueprint)
        if not fields:
            missing_fields.append({"fieldname": "metadata", "label": "Readable DocType metadata", "fieldtype": "Data"})
        missing_dependencies = self.dependency_service.detect_for_operation(doctype, data, operation="create", user=user, blueprint=blueprint)
        missing_dependencies = self.add_dependency_reviews(missing_dependencies, context=context, user=user)
        preflight = self.run_preflight_create(doctype, data, conversation_fields, missing_fields, missing_dependencies, user=user)
        preflight_field = preflight.get("field") if not preflight.get("valid") and preflight.get("recoverable", True) else None
        forced_field = forced_recovery_field(fields, data, setup_state)
        if forced_field:
            preflight_field = forced_field
            preflight = {
                **preflight,
                "field": forced_field,
                "fieldname": forced_field.get("fieldname"),
                "recovery_kind": "forced_field_collection",
                "guidance": f"I need {field_label(forced_field)} before I create this {doctype}.",
            }
        if preflight_field and any(field.get("fieldname") == preflight_field.get("fieldname") for field in missing_fields):
            preflight_field = None
        if missing_dependencies:
            preflight_field = None
        setup_field = None
        if not missing_fields and not missing_dependencies and preflight.get("valid"):
            setup_field = self.next_user_setup_field(doctype, data, fields, setup_state, user=user)
        preflight_missing = []
        if preflight_field:
            preflight_missing.append(field_label(preflight_field))
        elif not preflight.get("valid") and preflight.get("recoverable", True) and not missing_dependencies:
            preflight_missing.append("Talisma OneCampus validation")
        plan = self.operation_planner.build_create_plan(
            blueprint,
            data=data,
            supplied_data=supplied_data,
            defaults_applied=defaults_applied,
            missing_fields=missing_fields,
            dependencies=missing_dependencies,
            preflight={**preflight, "field": preflight_field},
            setup_field=setup_field,
        )
        next_field = plan.get("next_field")
        review = self.review_builder.build_creation_review(
            doctype,
            data=data,
            fields=conversation_fields,
            supplied_data=supplied_data,
            defaults_applied=defaults_applied,
            context=context,
            user=user,
        )
        prepared = {
            "operation": "create",
            "supported": True,
            "doctype": doctype,
            "blueprint": blueprint,
            "operation_plan": plan,
            "data": data,
            "display_fields": display_fields(data, conversation_fields),
            "defaults_applied": defaults_applied,
            "missing_fields": plan.get("missing_fields", []) + [item for item in preflight_missing if item not in (plan.get("missing_fields") or [])],
            "missing_dependencies": missing_dependencies,
            "validation_issues": preflight.get("issues") or [],
            "preflight": preflight,
            "review": review,
            "setup_state": setup_state,
            "setup_prompt": setup_field.get("prompt") if setup_field else None,
            "setup_actions": setup_field.get("setup_actions") if setup_field else [],
            "dependency_context": {
                "original_message": (context or {}).get("raw", {}).get("message"),
                "parsed_intent": getattr(intent, "structured_intent", None),
                "pending_action": "create",
                "workflow_step": "dependency_resolution",
            },
            "next_missing_field": self.creation_session.serialize_field(self.conversation_field(next_field, data), user=user) if next_field else None,
            "ready": plan.get("ready"),
        }
        if setup_field and prepared.get("next_missing_field"):
            prepared["next_missing_field"].update({key: setup_field.get(key) for key in ("wingman_setup", "child_fieldname", "child_fieldtype", "optional", "placeholder") if setup_field.get(key) is not None})
            if setup_field.get("component"):
                prepared["next_missing_field"]["component"] = setup_field.get("component")
            if setup_field.get("choices") is not None:
                prepared["next_missing_field"]["choices"] = setup_field.get("choices")
            if setup_field.get("required") is not None:
                prepared["next_missing_field"]["required"] = setup_field.get("required")
        if doctype == "Program" and prepared.get("next_missing_field"):
            self.apply_program_field_recommendation(prepared["next_missing_field"], data, user=user)
        prepared["message"] = self.format_prepared_create_message(prepared)
        return prepared

    def apply_program_field_recommendation(self, field, data, user=None):
        """Prefill editable Program fields from established OneCampus patterns."""
        fieldname = (field or {}).get("fieldname")
        program_name = str((data or {}).get("program_name") or "").strip()
        if not program_name or fieldname not in {
            "talisma_program_code",
            "program_abbreviation",
            "talisma_degree",
            "talisma_academic_unit",
        }:
            return field

        rows = self.program_pattern_rows(user=user)
        recommendation = recommend_program_values(program_name, rows).get(fieldname)
        if recommendation in (None, "", []):
            return field

        field["recommendation"] = {
            "value": recommendation,
            "label": str(recommendation),
            "reason": "Prefilled from the naming and academic patterns used by existing Programs.",
            "confidence": 95,
            "auto_apply": True,
            "editable": True,
        }
        if field.get("fieldtype") == "Link":
            choices = list(field.get("choices") or [])
            if not any(str(choice.get("value") or choice.get("label")) == str(recommendation) for choice in choices if isinstance(choice, dict)):
                choices.insert(0, {"label": str(recommendation), "value": recommendation})
            field["choices"] = choices
        return field

    def program_pattern_rows(self, user=None):
        response = self.erp_service.list_documents(
            "Program",
            fields=[
                "name",
                "program_name",
                "talisma_program_code",
                "program_abbreviation",
                "talisma_degree",
                "talisma_academic_unit",
            ],
            page_size=100,
            user=user,
        )
        result = (response or {}).get("result") or {}
        rows = result.get("rows") if isinstance(result, dict) else []
        return [row for row in (rows or []) if isinstance(row, dict)]

    def format_prepared_create_message(self, prepared):
        if prepared.get("setup_prompt") and prepared.get("next_missing_field") and not prepared.get("ready"):
            return prepared.get("setup_prompt")
        if prepared.get("next_missing_field") and not prepared.get("ready"):
            preflight = prepared.get("preflight") or {}
            return format_collection_prompt(prepared, reason=preflight.get("guidance") if not preflight.get("valid", True) else None)
        if prepared.get("missing_dependencies") or prepared.get("missing_link_dependencies"):
            return format_dependency_collection_prompt(prepared)
        if not (prepared.get("preflight") or {}).get("valid", True):
            return format_preflight_validation_prompt(prepared)
        if prepared.get("doctype") == "Talisma Student Group Hold" and prepared.get("ready"):
            return self.format_student_group_hold_review(prepared)
        return format_creation_review(prepared)

    def format_student_group_hold_review(self, prepared):
        data = prepared.get("data") or {}
        response = self.erp_service.list_documents(
            "Student Group Student",
            fields=["name"],
            filters={"parent": data.get("student_group"), "parenttype": "Student Group", "active": 1},
            page_size=100,
        )
        students = len((((response or {}).get("result") or {}).get("rows") or []))
        blocked = [
            label
            for fieldname, label in (
                ("blocks_registration", "Registration"),
                ("blocks_transcript", "Transcript"),
                ("blocks_graduation", "Graduation"),
                ("blocks_financial_activity", "Financial Activity"),
            )
            if data.get(fieldname)
        ]
        return "\n".join(
            [
                "Student Group Hold Review",
                "Please confirm this bulk hold before any student records are changed.",
                "",
                "Hold Details",
                f"- Student Group: {data.get('student_group')}",
                f"- Hold Type: {data.get('hold_type')}",
                f"- Hold Reason: {data.get('reason')}",
                f"- Effective From: {data.get('effective_from')}",
                f"- Effective To: {data.get('effective_to') or 'No end date'}",
                f"- Blocks: {', '.join(blocked)}",
                "",
                "Impact",
                f"- {students} current group member{'s' if students != 1 else ''} will receive an individual hold.",
                "- Existing unrelated holds will not be changed.",
                "",
                "Current Status",
                "- No Talisma OneCampus data has been changed yet.",
            ]
        )

    def run_preflight_create(self, doctype, data, fields, missing_fields=None, missing_dependencies=None, user=None):
        if not fields:
            return {"valid": True, "field": None, "fieldname": None, "issues": [], "guidance": None}
        return self.preflight.validate_create(doctype, data=data, fields=fields, user=user)

    def add_dependency_reviews(self, dependencies, context=None, user=None, depth=0):
        reviewed = []
        if depth > 8:
            return reviewed
        for dependency in dependencies or []:
            item = dict(dependency)
            target_doctype = item.get("target_doctype")
            create_data = dict(item.get("create_data") or {})
            blueprint = self.build_blueprint(target_doctype)
            fields = blueprint["fields"]["all"]
            defaulted_data, defaults_applied = self.apply_defaults(target_doctype, create_data, fields, context=context, user=user, blueprint=blueprint)
            conversation_fields = self.conversation_fields(fields, defaulted_data, doctype=target_doctype)
            missing_fields = self.get_missing_mandatory_fields(defaulted_data, conversation_fields, blueprint=blueprint)
            child_dependencies = self.dependency_service.detect_for_operation(target_doctype, defaulted_data, operation="create", user=user, blueprint=blueprint)
            child_dependencies = self.add_dependency_reviews(child_dependencies, context=context, user=user, depth=depth + 1)
            preflight = self.run_preflight_create(target_doctype, defaulted_data, conversation_fields, missing_fields, child_dependencies, user=user)
            preflight_field = preflight.get("field") if not preflight.get("valid") and preflight.get("recoverable", True) else None
            if preflight_field and any(field.get("fieldname") == preflight_field.get("fieldname") for field in missing_fields):
                preflight_field = None
            if child_dependencies:
                preflight_field = None
            next_field = missing_fields[0] if missing_fields else preflight_field
            preflight_missing = []
            if preflight_field:
                preflight_missing.append(field_label(preflight_field))
            elif not preflight.get("valid") and preflight.get("recoverable", True) and not child_dependencies:
                preflight_missing.append("Talisma OneCampus validation")
            item["create_data"] = defaulted_data
            item["missing_fields"] = [field_label(field) for field in missing_fields] + preflight_missing
            item["missing_dependencies"] = child_dependencies
            item["missing_link_dependencies"] = child_dependencies
            item["next_missing_field"] = self.creation_session.serialize_field(self.conversation_field(next_field, defaulted_data), user=user) if next_field else None
            item["validation_issues"] = preflight.get("issues") or []
            item["preflight"] = preflight
            item["ready"] = not missing_fields and not child_dependencies and preflight.get("valid")
            item["review"] = self.review_builder.build_creation_review(
                target_doctype,
                data=defaulted_data,
                fields=conversation_fields,
                supplied_data=create_data,
                defaults_applied=defaults_applied,
                context=context,
                user=user,
            )
            reviewed.append(item)
        return reviewed

    def sync_pending_draft(self, prepared, context=None):
        context = context or {}
        conversation_id = context.get("conversation_id")
        if not conversation_id or not prepared.get("supported"):
            return
        if prepared.get("cancelled"):
            clear_pending_create_draft(conversation_id, user=context.get("user"))
            return
        if prepared.get("ready") and not (prepared.get("missing_dependencies") or prepared.get("missing_link_dependencies")):
            clear_pending_create_draft(conversation_id, user=context.get("user"))
            return
        set_pending_create_draft(
            conversation_id,
            {
                "operation": "create",
                "doctype": prepared.get("doctype"),
                "data": prepared.get("data") or {},
                "next_field": prepared.get("next_missing_field"),
                "setup_state": prepared.get("setup_state") or {},
                "resume_action": prepared.get("resume_action"),
            },
            user=context.get("user"),
        )

    def create_record(self, doctype, data, user=None):
        if not self.is_supported_create_doctype(doctype):
            return {
                "success": False,
                "errors": [{"code": "unsupported_create_doctype", "message": f"Wingman does not create {doctype} records yet."}],
                "validation_issues": [],
            }

        blueprint = self.build_blueprint(doctype)
        data, _defaults_applied = self.apply_defaults(doctype, data or {}, blueprint["fields"]["all"], user=user, blueprint=blueprint)
        if doctype == "Talisma Curriculum Version":
            curriculum_code = data.get("curriculum_code")
            existing = self.erp_service.read_document(doctype, curriculum_code, user=user) if curriculum_code else None
            if existing and existing.get("success"):
                existing_data = existing.get("result") or {}
                existing_program = existing_data.get("program")
                requested_program = data.get("program")
                if existing_program and requested_program and existing_program != requested_program:
                    return {
                        "success": False,
                        "message": (
                            f"Curriculum code {curriculum_code} already belongs to {existing_program}. "
                            "Use a different Curriculum Code for this Program."
                        ),
                        "errors": [
                            {
                                "code": "curriculum_code_program_conflict",
                                "message": f"Curriculum code {curriculum_code} is already used by another Program.",
                            }
                        ],
                        "validation_issues": [],
                    }
                response = self.erp_service.update_document(doctype, curriculum_code, data=data, user=user)
                if response.get("success"):
                    response["updated_existing"] = True
                    response["message"] = f"Completed existing Curriculum Version {curriculum_code}."
                return response
        return self.erp_service.create_document(doctype, data=data or {}, user=user)

    def resolve_create_doctype(self, message, intent=None):
        return resolve_create_doctype(message, intent=intent, erp_service=self.erp_service)

    def is_supported_create_doctype(self, doctype):
        if not doctype:
            return False
        blueprint = self.build_blueprint(doctype)
        if not blueprint.get("metadata"):
            return False
        metadata = blueprint.get("metadata") or {}
        if metadata.get("is_child_table") or metadata.get("istable"):
            return False
        return bool(blueprint.get("doctype") == doctype or blueprint.get("fields", {}).get("all"))

    def get_metadata(self, doctype):
        response = self.erp_service.get_metadata(doctype)
        if isinstance(response, dict):
            return response.get("result") or {}
        return response or {}

    def build_blueprint(self, doctype, metadata=None):
        return self.blueprint_builder.build(doctype, metadata=metadata or self.get_metadata(doctype))

    def apply_defaults(self, doctype, data, fields=None, context=None, user=None, blueprint=None):
        blueprint = blueprint or self.build_blueprint(doctype)
        fields = fields or blueprint["fields"]["all"]
        payload = dict(data or {})
        defaults_applied = []
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}

        self.apply_context_defaults(doctype, payload, field_map, context=context, defaults_applied=defaults_applied, blueprint=blueprint)
        self.apply_curriculum_program_defaults(doctype, payload, field_map, user=user, defaults_applied=defaults_applied)
        self.apply_metadata_defaults(payload, fields, user=user, defaults_applied=defaults_applied, blueprint=blueprint, doctype=doctype)
        self.apply_safe_inferred_defaults(payload, fields, user=user, defaults_applied=defaults_applied, blueprint=blueprint)
        return clean_payload(normalize_payload_values(payload, fields), fields), defaults_applied

    def apply_curriculum_program_defaults(self, doctype, payload, field_map, user=None, defaults_applied=None):
        if doctype != "Talisma Curriculum Version" or payload.get("degree") not in (None, "", []):
            return
        program = payload.get("program")
        if not program:
            return
        response = self.erp_service.read_document("Program", program, user=user)
        document = (response or {}).get("result") if isinstance(response, dict) else None
        degree = (document or {}).get("talisma_degree") or (document or {}).get("degree")
        if degree:
            self.set_default(
                payload,
                field_map,
                "degree",
                degree,
                defaults_applied if defaults_applied is not None else [],
                f"Associated with Program {program}.",
            )

    def apply_context_defaults(self, doctype, payload, field_map, context=None, defaults_applied=None, blueprint=None):
        defaults_applied = defaults_applied if defaults_applied is not None else []
        context_object = (context or {}).get("object") or {}
        source_doctype = context_object.get("doctype")
        source_docname = context_object.get("docname")
        if not source_doctype or not source_docname:
            return

        for field in (blueprint or {}).get("fields", {}).get("links", []):
            if field.get("fieldtype") == "Link" and field.get("options") == source_doctype:
                self.set_default(payload, field_map, field.get("fieldname"), source_docname, defaults_applied, "Current page context.")

        for field in (blueprint or {}).get("fields", {}).get("links", []):
            if field.get("fieldtype") != "Dynamic Link":
                continue
            selector = field_map.get(field.get("options"))
            if selector and select_supports_value(selector, source_doctype):
                self.set_default(payload, field_map, selector.get("fieldname"), source_doctype, defaults_applied, "Current page context.")
                self.set_default(payload, field_map, field.get("fieldname"), source_docname, defaults_applied, "Current page context.")

        for selector in field_map.values():
            if selector.get("fieldtype") == "Select" and select_supports_value(selector, source_doctype):
                linked = next(
                    (
                        field
                        for field in (blueprint or {}).get("fields", {}).get("links", [])
                        if field.get("fieldtype") == "Link" and field.get("options") == source_doctype
                    ),
                    None,
                )
                if linked:
                    self.set_default(payload, field_map, selector.get("fieldname"), source_doctype, defaults_applied, "Current page context.")
                    self.set_default(payload, field_map, linked.get("fieldname"), source_docname, defaults_applied, "Current page context.")

    def apply_metadata_defaults(self, payload, fields, user=None, defaults_applied=None, blueprint=None, doctype=None):
        defaults_applied = defaults_applied if defaults_applied is not None else []
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
        primary_fieldname = ((blueprint or {}).get("primary_field") or {}).get("fieldname")
        for field in fields:
            fieldname = field.get("fieldname")
            if doctype == "Talisma Curriculum Version" and fieldname == "minimum_residency_credits":
                continue
            if not is_editable_business_field(field):
                continue
            if not fieldname or payload.get(fieldname) not in (None, "", []):
                continue
            if not can_use_metadata_default(field, primary_fieldname=primary_fieldname):
                continue

            value = field.get("default")
            if value in (None, "") and field.get("fieldtype") == "Check" and is_required(field):
                value = 0
            value = normalize_metadata_default(value)
            if value in (None, "") and field.get("fieldtype") == "Link" and is_required(field):
                value = self.resolve_link_default(field, user=user)

            self.set_default(payload, field_map, fieldname, value, defaults_applied, "Talisma OneCampus metadata default.")

    def apply_safe_inferred_defaults(self, payload, fields, user=None, defaults_applied=None, blueprint=None):
        defaults_applied = defaults_applied if defaults_applied is not None else []
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
        for field in (blueprint or {}).get("fields", {}).get("editable", []):
            fieldname = field.get("fieldname")
            if not fieldname or payload.get(fieldname) not in (None, "", []):
                continue
            if field.get("fieldtype") == "Check":
                self.set_default(payload, field_map, fieldname, 0, defaults_applied, "Talisma OneCampus boolean default.")
            elif field.get("fieldtype") == "Link" and is_required(field) and can_use_metadata_default(field):
                self.set_default(payload, field_map, fieldname, self.resolve_link_default(field, user=user), defaults_applied, "Existing linked record.")

    def resolve_link_default(self, field, user=None):
        field = field or {}
        target_doctype = field.get("options")
        if not target_doctype:
            return None
        choices = self.link_resolution.search(target_doctype, text="", user=user, page_size=10).get("rows") or []
        value = choose_default_link_value(field, choices)
        if value and self.link_exists(target_doctype, value, user=user):
            return value
        for candidate in root_link_candidates(target_doctype):
            if self.link_exists(target_doctype, candidate, user=user):
                return candidate
        return None

    def resolve_existing_link(self, doctype, candidates, user=None):
        for candidate in candidates or []:
            response = self.erp_service.read_document(doctype, candidate, user=user)
            if response.get("success"):
                return candidate
        return None

    def set_default(self, payload, field_map, fieldname, value, defaults_applied, reason):
        if fieldname not in field_map or value in (None, "", []):
            return
        if payload.get(fieldname) not in (None, "", []):
            return
        payload[fieldname] = normalize_field_value(field_map[fieldname], value)
        source = source_from_reason(reason)
        defaults_applied.append(
            {
                "fieldname": fieldname,
                "label": field_label(field_map[fieldname]),
                "value": payload[fieldname],
                "source": source,
                "confidence": int(confidence_for_source(source) * 100),
                "reason": reason,
            }
        )

    def get_missing_mandatory_labels(self, data, fields):
        return [field_label(field) for field in self.get_missing_mandatory_fields(data, fields)]

    def get_missing_mandatory_fields(self, data, fields=None, blueprint=None):
        missing = []
        seen = set()
        for field in fields or []:
            fieldname = field.get("fieldname")
            if not fieldname or fieldname in seen:
                continue
            if not is_editable_business_field(field):
                continue
            if not field_is_required_for_conversation(field, data):
                continue
            if data.get(fieldname) in (None, "", []):
                missing.append(field)
                seen.add(fieldname)
        return missing

    def parse_answer_for_field(self, message, field, user=None):
        if field.get("wingman_recovery") == "alternative_field_choice":
            return parse_recovery_alternative_choice(message, field)

        if field.get("wingman_setup") == "curriculum_requirements":
            try:
                submitted = json.loads(str(message or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                submitted = None
            if submitted == []:
                return {
                    "accepted": False,
                    "message": "Add at least one Course to Curriculum Requirements before continuing.",
                }
            value = parse_curriculum_requirements(message)
            if value in (None, ""):
                return {"accepted": False, "message": "Add at least one valid Course and Requirement Type before continuing."}
            return {
                "accepted": True,
                "value": value,
                "setup_state": {"curriculum_requirements_reviewed": True},
            }

        if field.get("wingman_setup") == "student_group_members":
            try:
                submitted = json.loads(str(message or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                submitted = parse_multi_value(message)
            if not isinstance(submitted, list):
                submitted = []
            students = []
            seen = set()
            for item in submitted:
                student = item.get("student") if isinstance(item, dict) else item
                student = clean_query(student)
                if not student or student in seen:
                    continue
                seen.add(student)
                response = self.erp_service.read_document("Student", student, user=user)
                profile = (response or {}).get("result") if isinstance(response, dict) else None
                student_name = (profile or {}).get("student_name") or (profile or {}).get("student_full_name")
                if not student_name:
                    continue
                students.append({"student": student, "student_name": student_name, "active": 1})
            if not students:
                return {"accepted": False, "message": "Select at least one Student before continuing."}
            return {
                "accepted": True,
                "value": students,
                "setup_state": {"student_group_members_reviewed": True},
            }

        if field.get("wingman_setup") == "user_roles":
            normalized = normalize(message)
            if normalized in CONTINUE_WITHOUT_ROLES:
                return {"accepted": True, "value": [], "setup_state": {"roles_reviewed": True}}
            values = parse_multi_value(message)
            if not values:
                return {"accepted": False, "message": "Please select at least one Role or choose Continue Anyway."}
            child_fieldname = field.get("child_fieldname") or "role"
            return {
                "accepted": True,
                "value": [{child_fieldname: item} for item in values],
                "setup_state": {"roles_reviewed": True},
            }

        if field.get("wingman_setup") == "module_profile":
            normalized = normalize(message)
            if normalized in SKIP_OPTIONAL_SETUP:
                return {"accepted": True, "value": None, "setup_state": {"module_profile_reviewed": True}}

        value = parse_field_answer(message, field)
        if value in (None, "", []):
            return {"accepted": False, "message": f"I could not read a valid value for {field_label(field)}."}

        if field.get("wingman_dynamic_target_selector"):
            matched = match_select_option(field, value)
            if not matched:
                options = split_options(field.get("options"))
                option_text = ", ".join(options[:6]) if options else "a valid option"
                return {"accepted": False, "message": f"Please choose a valid {field_label(field)} option: {option_text}."}
            return {"accepted": True, "value": matched}

        if field.get("fieldtype") == "Select":
            matched = match_select_option(field, value)
            if not matched:
                options = split_options(field.get("options"))
                option_text = ", ".join(options[:6]) if options else "a valid option"
                return {"accepted": False, "message": f"Please choose a valid {field_label(field)} option: {option_text}."}
            value = matched

        if field.get("fieldtype") == "Link":
            resolved = self.link_resolution.resolve_value(field, value, user=user)
            if not resolved.get("accepted"):
                return resolved
            payload = {"accepted": True, "value": normalize_field_value(field, resolved.get("value"))}
            if resolved.get("missing_dependency"):
                payload["missing_dependency"] = resolved.get("missing_dependency")
            if resolved.get("matches"):
                payload["matches"] = resolved.get("matches")
            return payload

        if field.get("fieldtype") == "Dynamic Link":
            target_doctype = dynamic_link_target(field, {})
            if not target_doctype:
                return {"accepted": False, "message": f"Please choose {field_label(field)} first."}
            link_field = {**field, "fieldtype": "Link", "options": target_doctype, "label": target_doctype}
            resolved = self.link_resolution.resolve_value(link_field, value, user=user)
            if not resolved.get("accepted"):
                return resolved
            payload = {"accepted": True, "value": normalize_field_value(field, resolved.get("value"))}
            if resolved.get("missing_dependency"):
                payload["missing_dependency"] = resolved.get("missing_dependency")
            if resolved.get("matches"):
                payload["matches"] = resolved.get("matches")
            return payload

        return {"accepted": True, "value": normalize_field_value(field, value)}

    def link_exists(self, doctype, docname, user=None):
        response = self.erp_service.read_document(doctype, docname, user=user)
        return bool(response.get("success"))

    def next_user_setup_field(self, doctype, data, fields, setup_state, user=None):
        if doctype == "Talisma Curriculum Version" and not setup_state.get("curriculum_requirements_reviewed"):
            requirements_field = next((field for field in self.conversation_fields(fields, data, doctype=doctype) if field.get("fieldname") == "requirements"), None)
            if requirements_field:
                serialized = self.creation_session.serialize_field(requirements_field, user=user)
                serialized.update(
                    {
                        "wingman_setup": "curriculum_requirements",
                        "required": True,
                        "optional": False,
                        "prompt": "\n".join(
                            [
                                "Curriculum Requirements",
                                "Add at least one Course before continuing.",
                                "Requirement Code and Sequence are assigned automatically in the order Courses are added.",
                            ]
                        ),
                    }
                )
                return serialized
        if doctype == "Student Group" and not setup_state.get("student_group_members_reviewed"):
            members_field = self.student_group_members_field(fields, user=user)
            if members_field:
                return members_field
        if doctype != "User":
            return None
        roles_field = self.user_roles_field(fields, user=user)
        if roles_field and not data.get("roles") and not setup_state.get("roles_reviewed"):
            return roles_field
        module_profile_field = self.user_module_profile_field(fields, user=user)
        if module_profile_field and not data.get(module_profile_field.get("fieldname")) and not setup_state.get("module_profile_reviewed"):
            return module_profile_field
        return None

    def student_group_members_field(self, fields, user=None):
        members_field = next(
            (
                field for field in fields or []
                if field.get("fieldname") == "students"
                and field.get("fieldtype") in ("Table", "Table MultiSelect")
            ),
            None,
        )
        if not members_field:
            return None
        student_field = self.primary_child_value_field(members_field.get("options"))
        if not student_field or student_field.get("options") != "Student":
            return None
        choices = self.creation_session.link_choices("Student", user=user)
        choices = [
            {"label": choice.get("label"), "value": choice.get("value")}
            for choice in choices
            if choice.get("label") and choice.get("value")
        ]
        return {
            "fieldname": "students",
            "label": "Select Students",
            "fieldtype": members_field.get("fieldtype"),
            "options": members_field.get("options"),
            "wingman_setup": "student_group_members",
            "child_fieldname": student_field.get("fieldname") or "student",
            "child_fieldtype": student_field.get("fieldtype"),
            "required": True,
            "optional": False,
            "component": {
                "type": "student_group_members",
                "target_doctype": "Student",
                "search_method": LINK_SEARCH_METHOD,
                "allow_create": False,
                "allow_create_missing": False,
                "hide_descriptions": True,
            },
            "choices": choices,
            "placeholder": "Search students by name",
            "prompt": "Select the students who should belong to this Student Group.",
        }

    def user_roles_field(self, fields, user=None):
        roles_field = next((field for field in fields or [] if field.get("fieldname") == "roles" and field.get("fieldtype") in ("Table", "Table MultiSelect")), None)
        if not roles_field:
            return None
        child_field = self.primary_child_value_field(roles_field.get("options"))
        if not child_field:
            return None
        target_doctype = child_field.get("options")
        serialized = self.creation_session.serialize_field(child_field, user=user)
        serialized.update(
            {
                "fieldname": "roles",
                "label": field_label(roles_field),
                "fieldtype": roles_field.get("fieldtype"),
                "options": roles_field.get("options"),
                "wingman_setup": "user_roles",
                "child_fieldname": child_field.get("fieldname"),
                "child_fieldtype": child_field.get("fieldtype"),
                "required": False,
                "optional": True,
                "component": {
                    "type": "multiselect",
                    "target_doctype": target_doctype,
                    "search_method": LINK_SEARCH_METHOD,
                },
                "choices": self.creation_session.link_choices(target_doctype, user=user) if target_doctype else [],
                "placeholder": "Select one or more Roles",
                "prompt": "\n".join(
                    [
                        "Assign Roles",
                        "This User currently has no Talisma OneCampus Roles assigned.",
                        "Users without Roles will not be able to access Talisma OneCampus functionality.",
                        "",
                        "Choose one or more Roles, or continue without Roles.",
                    ]
                ),
                "setup_actions": [
                    {
                        "type": "send_message",
                        "label": "Continue Anyway",
                        "payload": {"message": "continue anyway"},
                        "requires_confirmation": False,
                        "auto_execute": False,
                        "enabled": True,
                    }
                ],
            }
        )
        return serialized

    def user_module_profile_field(self, fields, user=None):
        field = next((item for item in fields or [] if item.get("fieldtype") == "Link" and item.get("options") == "Module Profile" and is_editable_business_field(item)), None)
        if not field:
            return None
        choices = self.creation_session.link_choices("Module Profile", user=user)
        if not choices:
            return None
        serialized = self.creation_session.serialize_field(field, user=user)
        serialized.update(
            {
                "wingman_setup": "module_profile",
                "required": False,
                "optional": True,
                "choices": choices,
                "prompt": "\n".join(
                    [
                        "Module Profile",
                        "Module Profiles are available in Talisma OneCampus.",
                        "Choose one for this User, or skip this step.",
                    ]
                ),
                "setup_actions": [
                    {
                        "type": "send_message",
                        "label": "Skip",
                        "payload": {"message": "skip"},
                        "requires_confirmation": False,
                        "auto_execute": False,
                        "enabled": True,
                    }
                ],
            }
        )
        return serialized

    def primary_child_value_field(self, child_doctype):
        metadata = self.get_metadata(child_doctype)
        fields = metadata.get("fields") or []
        candidates = [field for field in fields if is_editable_business_field(field) and is_required(field)]
        candidates = candidates or [field for field in fields if is_editable_business_field(field)]
        return candidates[0] if candidates else None

    def conversation_fields(self, fields, data, doctype=None):
        controller_targets = dynamic_link_controller_targets(fields, doctype=doctype)
        result = [self.conversation_field(field, data, controller_targets=controller_targets) for field in fields or []]
        if doctype != "Talisma Curriculum Version":
            return result

        priority = {
            "program": 0,
            "degree": 1,
            "catalog_year": 2,
            "curriculum_code": 3,
            "version_label": 4,
            "effective_from": 5,
            "effective_to": 6,
            "minimum_total_credits": 7,
            "minimum_residency_credits": 8,
            "requirements": 9,
            "notes": 10,
        }
        for field in result:
            fieldname = field.get("fieldname")
            if fieldname in {"effective_to", "minimum_residency_credits"}:
                field["reqd"] = 1
                field["required"] = True
            if fieldname == "minimum_residency_credits":
                field["label"] = "Minimum Hours"
                field["placeholder"] = "Enter minimum hours"
            if fieldname == "requirements":
                # The dedicated Curriculum Requirements step enforces this
                # mandatory table. Exclude it from generic field collection so
                # Course and Requirement Type remain in one purpose-built form.
                field["reqd"] = 0
                field["mandatory"] = False
                field["component"] = {
                    "type": "curriculum_requirements",
                    "program": data.get("program"),
                    "minimum_total_credits": data.get("minimum_total_credits"),
                    "course_field": {
                        "fieldname": "course",
                        "label": "Course",
                        "fieldtype": "Link",
                        "options": "Course",
                        "placeholder": "Search and select a Course",
                        "component": {
                            "type": "link",
                            "target_doctype": "Course",
                            "search_method": LINK_SEARCH_METHOD,
                            "allow_create": False,
                            "allow_create_missing": False,
                        },
                    },
                    "requirement_types": ["Required Course", "Course Group", "Minimum Credits"],
                }
                field["choices"] = self.creation_session.link_choices("Course")
                field["placeholder"] = "Add curriculum requirements"
        return sorted(result, key=lambda field: (priority.get(field.get("fieldname"), 100), result.index(field)))

    def conversation_field(self, field, data, controller_targets=None):
        field = dict(field or {})
        target_options = (controller_targets or {}).get(field.get("fieldname")) or []
        if target_options:
            field["wingman_dynamic_target_selector"] = True
            field["original_fieldtype"] = field.get("fieldtype")
            field["original_options"] = field.get("options")
            field["options"] = "\n".join(target_options)
            field["choices"] = [{"label": item, "value": item} for item in target_options]
            field["placeholder"] = f"Choose {field_label(field)}"
            field["component"] = {"type": "select", "options": target_options}
            return field
        if field.get("fieldtype") != "Dynamic Link":
            return field
        target_doctype = dynamic_link_target(field, data)
        if not target_doctype:
            return field
        field["target_doctype"] = target_doctype
        field["label"] = target_doctype
        field["placeholder"] = f"Search or select {target_doctype}"
        component = dict(field.get("component") or {})
        component.update(
            {
                "type": "dynamic_link",
                "dynamic_target_field": field.get("options"),
                "target_doctype": target_doctype,
                "search_method": LINK_SEARCH_METHOD,
                "allow_create": True,
                "allow_create_missing": True,
            }
        )
        field["component"] = component
        return field


def forced_recovery_field(fields, data, setup_state):
    fieldname = (setup_state or {}).get("recovery_forced_fieldname")
    if not fieldname or (data or {}).get(fieldname) not in (None, "", []):
        return None
    for field in fields or []:
        if field.get("fieldname") == fieldname and is_editable_business_field(field):
            return field
    return None


def field_is_required_for_conversation(field, data):
    if is_required(field):
        return True
    if is_conditionally_required(field, data):
        return True
    return is_active_dynamic_link_field(field, data)


def is_active_dynamic_link_field(field, data):
    if (field or {}).get("fieldtype") != "Dynamic Link":
        return False
    target_doctype = dynamic_link_target(field, data)
    fieldname = (field or {}).get("fieldname")
    return bool(target_doctype and fieldname and (data or {}).get(fieldname) in (None, "", []))


def dynamic_link_controller_targets(fields, doctype=None):
    field_map = {field.get("fieldname"): field for field in fields or [] if field.get("fieldname")}
    targets_by_controller = {}
    for dynamic_field in fields or []:
        if dynamic_field.get("fieldtype") != "Dynamic Link":
            continue
        controller_fieldname = dynamic_field.get("options")
        controller_field = field_map.get(controller_fieldname)
        if not controller_field:
            continue
        targets = dynamic_link_target_options(controller_field, dynamic_field, doctype=doctype)
        if not targets:
            continue
        existing = targets_by_controller.setdefault(controller_fieldname, [])
        for target in targets:
            if target not in existing:
                existing.append(target)
    return targets_by_controller


def dynamic_link_target_options(controller_field, dynamic_field=None, doctype=None):
    options = []
    if (controller_field or {}).get("fieldtype") == "Select":
        options.extend(split_options((controller_field or {}).get("options")))
    if (controller_field or {}).get("fieldtype") == "Link" and (controller_field or {}).get("options") == "DocType":
        options.extend(extract_doc_type_filter_options(controller_field))
        options.extend(extract_doc_type_filter_options(dynamic_field))
    if not options:
        options.extend(standard_dynamic_link_targets(doctype, controller_field))
    return unique_values(options)


def extract_doc_type_filter_options(field):
    options = []
    for key in ("filters", "link_filters", "query_filters", "search_filters", "get_query"):
        options.extend(extract_filter_options((field or {}).get(key)))
    return unique_values(options)


def extract_filter_options(value):
    if value in (None, "", []):
        return []
    if isinstance(value, dict):
        options = []
        for item in value.values():
            options.extend(extract_filter_options(item))
        return options
    if isinstance(value, (list, tuple)):
        if len(value) >= 3 and normalize(value[1]) in {"in", "not in"}:
            return extract_filter_options(value[2])
        if len(value) >= 4 and normalize(value[2]) in {"in", "not in"}:
            return extract_filter_options(value[3])
        if all(isinstance(item, str) for item in value):
            return [item for item in value if looks_like_doctype_option(item)]
        options = []
        for item in value:
            options.extend(extract_filter_options(item))
        return options
    if isinstance(value, str):
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", value)
        return [item for item in quoted if looks_like_doctype_option(item)]
    return []


def looks_like_doctype_option(value):
    text = clean_query(value)
    if not text:
        return False
    if normalize(text) in {"doctype", "doc type", "name", "in", "not in", "filters", "filter"}:
        return False
    if text.startswith("_"):
        return False
    return bool(re.search(r"[A-Za-z]", text))


def standard_dynamic_link_targets(doctype, controller_field):
    key = (doctype or parent_doctype(controller_field), (controller_field or {}).get("fieldname"))
    return list(STANDARD_DYNAMIC_LINK_TARGETS.get(key, ()))


def parent_doctype(field):
    return (field or {}).get("parent") or (field or {}).get("parent_doctype")


def unique_values(values):
    unique = []
    seen = set()
    for value in values or []:
        text = clean_query(value)
        if not text:
            continue
        key = normalize(text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def dynamic_link_target(field, data):
    field = field or {}
    if field.get("fieldtype") != "Dynamic Link":
        return field.get("options")
    controller = field.get("options")
    return (data or {}).get(controller) or field.get("target_doctype") or (field.get("component") or {}).get("target_doctype")


def is_conditionally_required(field, data):
    expression = (field or {}).get("mandatory_depends_on")
    if not expression:
        return False
    text = str(expression).strip()
    if not text:
        return False
    if text.startswith("eval:"):
        return eval_depends_on_expression(text[5:], data or {})
    if text.startswith("doc."):
        return bool((data or {}).get(text.split(".", 1)[1]))
    return bool((data or {}).get(text))


def eval_depends_on_expression(expression, data):
    expression = str(expression or "")
    equality = re.search(r"doc\.(?P<fieldname>[A-Za-z_][A-Za-z0-9_]*)\s*={2,3}\s*['\"](?P<value>[^'\"]+)['\"]", expression)
    if equality:
        return str((data or {}).get(equality.group("fieldname")) or "") == equality.group("value")

    inequality = re.search(r"doc\.(?P<fieldname>[A-Za-z_][A-Za-z0-9_]*)\s*!\={1,2}\s*['\"](?P<value>[^'\"]+)['\"]", expression)
    if inequality:
        return str((data or {}).get(inequality.group("fieldname")) or "") != inequality.group("value")

    referenced_fields = re.findall(r"doc\.([A-Za-z_][A-Za-z0-9_]*)", expression)
    if referenced_fields:
        return all(bool((data or {}).get(fieldname)) for fieldname in referenced_fields)
    return False


def parse_recovery_alternative_choice(message, field):
    requested = normalize(message)
    alternatives = field.get("alternatives") or []
    for item in alternatives:
        label = normalize(item.get("label"))
        value = normalize(item.get("value"))
        if requested in {label, value} or requested in label or label in requested:
            return {"accepted": True, "value": None, "setup_state": {"recovery_forced_fieldname": item.get("value")}}
    choices = ", ".join(item.get("label") for item in alternatives if item.get("label"))
    return {"accepted": False, "message": f"Please choose one option: {choices or 'the available option'}."}


def resolve_create_doctype(message, intent=None, erp_service=None):
    structured = getattr(intent, "structured_intent", None) or {}
    entity = structured.get("detected_entity") or {}
    entity_value = entity.get("value")
    text = normalize(message)

    known_doctypes = [{"name": name} for name in sorted(SUPPORTED_CREATE_DOCTYPES)]
    known_doctype_names = {item["name"] for item in known_doctypes}
    known_match = resolve_create_doctype_from_candidates(text, entity_value, known_doctypes, known_doctype_names)
    if known_match:
        return known_match

    doctypes = discover_create_doctypes(erp_service)
    doctype_names = {item["name"] for item in doctypes}
    return resolve_create_doctype_from_candidates(text, entity_value, doctypes, doctype_names)


def resolve_create_doctype_from_candidates(text, entity_value, doctypes, doctype_names):
    # The record type explicitly named immediately after the create verb must
    # win over an inferred entity. For example, in "create a curriculum for
    # Bachelor's in Computer Application", Program is the linked value after
    # "for"; it is not the record type being created.
    explicit_alias = resolve_alias_from_create_text(text, doctype_names)
    if explicit_alias:
        return explicit_alias

    if entity_value in doctype_names:
        return entity_value
    if entity_value in ENTITY_DOCTYPE_OVERRIDES:
        return ENTITY_DOCTYPE_OVERRIDES[entity_value]

    explicit = resolve_doctype_from_create_text(text, doctypes)
    if explicit:
        return explicit

    for doctype, aliases in sorted(ENTITY_ALIASES.items(), key=lambda item: max(len(alias) for alias in item[1]), reverse=True):
        if doctype in doctype_names and any(contains_phrase(text, alias) for alias in aliases):
            return doctype
    return None


def resolve_alias_from_create_text(text, doctype_names):
    normalized_text = normalize(text)
    if not any(
        normalized_text == word or normalized_text.startswith(f"{word} ")
        for word in CREATE_WORDS
    ):
        return None

    target_text = strip_create_prefix(normalized_text)
    if not target_text:
        return None

    candidates = []
    for doctype, aliases in ENTITY_ALIASES.items():
        if doctype not in doctype_names:
            continue
        for alias in set(aliases or ()) | {doctype}:
            normalized_alias = normalize(alias)
            if normalized_alias:
                candidates.append((normalized_alias, doctype))

    for alias, doctype in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        if target_text == alias or target_text.startswith(f"{alias} "):
            return doctype
    return None


def discover_create_doctypes(erp_service=None):
    rows = []
    if erp_service is not None:
        metadata_service = getattr(erp_service, "metadata_service", None)
        if metadata_service and hasattr(metadata_service, "list_doctypes"):
            try:
                rows = metadata_service.list_doctypes(include_child_tables=False) or []
            except Exception:
                rows = []
        if not rows and hasattr(erp_service, "metadata") and isinstance(getattr(erp_service, "metadata"), dict):
            rows = [{"name": name} for name in erp_service.metadata.keys()]

    names = {doctype_name(item) for item in rows}
    return [{"name": name} for name in sorted(names) if name]


def doctype_name(row):
    if isinstance(row, dict):
        return row.get("name") or row.get("doctype")
    return getattr(row, "name", None) or getattr(row, "doctype", None) or str(row or "")


def resolve_doctype_from_create_text(text, doctypes):
    target_text = strip_create_prefix(text)
    if not target_text:
        return None
    ranked = sorted((item.get("name") for item in doctypes if item.get("name")), key=len, reverse=True)
    for doctype in ranked:
        normalized = normalize(doctype)
        if target_text == normalized or target_text.startswith(f"{normalized} "):
            return doctype
    return None


def strip_create_prefix(text):
    value = normalize(text)
    for word in CREATE_WORDS:
        if value == word:
            return ""
        prefix = f"{word} "
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
            break
    return re.sub(r"^(?:a|an|the|new)\s+", "", value).strip()


def extract_create_data(message, doctype, fields, intent=None, blueprint=None):
    data = {}
    fieldnames = {field.get("fieldname") for field in fields if field.get("fieldname")}
    if doctype == "Talisma Curriculum Version":
        program = extract_curriculum_program(message)
        if program and "program" in fieldnames:
            data["program"] = program
        catalog_year = extract_catalog_year(message)
        if catalog_year and "catalog_year" in fieldnames:
            data["catalog_year"] = catalog_year
        name = None
    else:
        name = extract_record_name(message, doctype)
    primary_field = primary_name_field(doctype, fields, blueprint=blueprint)
    if name and primary_field:
        data[primary_field] = name

    structured = getattr(intent, "structured_intent", None) or {}
    for entity in structured.get("entities") or []:
        if entity.get("entity_type") == "Email":
            set_first_existing(data, fieldnames, ("email_id", "email"), entity.get("value"))
        if entity.get("entity_type") == "Phone":
            set_first_existing(data, fieldnames, ("mobile_no", "phone", "phone_no"), entity.get("value"))

    set_first_existing(data, fieldnames, ("source", "lead_source"), extract_source_value(message))
    set_first_existing(data, fieldnames, ("territory", "region", "area"), extract_named_value(message, ("territory", "region", "area")))
    set_first_matching_field(data, fields, amount_field_candidates, extract_business_amount(message))
    set_first_matching_field(data, fields, assignment_field_candidates, extract_assignment_value(message))

    if name and "first_name" in fieldnames and "last_name" in fieldnames:
        parts = name.split()
        if "last_name" in fieldnames and len(parts) > 1:
            data["last_name"] = " ".join(parts[1:])
            data["first_name"] = data.get("first_name") or parts[0]

    if data.get("email") and "first_name" in fieldnames and not data.get("first_name"):
        data["first_name"] = title_from_email(data["email"])

    return clean_payload(data)


def extract_curriculum_program(message):
    text = str(message or "").strip()
    match = re.search(
        r"\bcurriculum(?:\s+version)?\s+(?:for|of)\s+(.+?)(?:\s+(?:catalog\s+year|year|effective\s+from|starting)\b|$)",
        text,
        re.IGNORECASE,
    )
    return clean_query(match.group(1)) if match else None


def extract_catalog_year(message):
    text = str(message or "")
    match = re.search(r"\b(?:catalog\s+year|academic\s+year|year)\s*(?:is|=|:)?\s*(20\d{2}(?:\s*[-/]\s*20\d{2})?)\b", text, re.IGNORECASE)
    return re.sub(r"\s+", "", match.group(1)) if match else None


def extract_source_value(message):
    text = message or ""
    explicit = extract_named_value(text, ("lead source", "source", "source to", "via"))
    if explicit:
        return explicit

    match = re.search(r"\bfrom\s+the\s+([A-Za-z][A-Za-z0-9 .&_-]{1,60})(?:\s+channel)\b", text, re.IGNORECASE)
    if match:
        return clean_query(re.sub(r"\bchannel\b", "", match.group(1), flags=re.IGNORECASE))
    return None


def extract_named_value(message, aliases):
    text = message or ""
    for alias in aliases or ():
        match = re.search(rf"\b{re.escape(alias)}\s*(?:is|=|:|to)?\s+([A-Za-z][A-Za-z0-9 .&_-]{{1,80}})", text, re.IGNORECASE)
        if match:
            value = re.split(r"\b(?:with|and|email|phone|number|status|source|territory|region|area|customer|supplier|item|date|amount|currency)\b", match.group(1), flags=re.IGNORECASE)[0]
            return clean_query(re.sub(r"\bchannel\b", "", value, flags=re.IGNORECASE))
    return None


def extract_record_name(message, doctype):
    text = message or ""
    quoted = re.search(r"['\"]([^'\"]{2,120})['\"]", text)
    if quoted:
        return clean_query(quoted.group(1))

    named = re.search(r"\b(?:named|called|name)\s+([A-Za-z][A-Za-z0-9 .&_'’\-]{1,120})", text, re.IGNORECASE)
    if named:
        return clean_record_name_for_doctype(named.group(1), doctype)

    aliases = sorted(set(ENTITY_ALIASES.get(doctype, ())) | {doctype}, key=len, reverse=True)
    create_prefix = r"(?:%s)" % "|".join(re.escape(word) for word in CREATE_WORDS)
    for alias in aliases:
        pattern = rf"\b{create_prefix}\s+(?:a|an|the|new)?\s*{re.escape(alias)}\s+(?:for\s+|named\s+|called\s+)?([A-Za-z][A-Za-z0-9 .&_'’\-]{{1,120}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_record_name_for_doctype(match.group(1), doctype)
    return None


def primary_name_field(doctype, fields, blueprint=None):
    if blueprint and blueprint.get("primary_field"):
        return blueprint["primary_field"].get("fieldname")
    fieldnames = {field.get("fieldname") for field in fields if field.get("fieldname")}
    configured = first_existing_field(PRIMARY_NAME_FIELDS.get(doctype, ()), fieldnames)
    if configured:
        return configured

    normalized = scrub(doctype)
    for candidate in (f"{normalized}_name", "title", "subject"):
        if candidate in fieldnames:
            return candidate

    for field in fields or []:
        fieldname = field.get("fieldname")
        if (
            field.get("fieldtype") == "Data"
            and is_required(field)
            and fieldname
            and fieldname != "name"
            and not field.get("hidden")
            and not field.get("read_only")
        ):
            return fieldname
    return None


def clean_record_name(value):
    value = EMAIL_PATTERN.sub("", value or "")
    value = re.sub(r"^\s*(?:named|called|name)\s+", "", value or "", flags=re.IGNORECASE)
    value = re.split(
        r"\b(?:with|from|in|via|for|to|using|under|email|worth|valued|value|amount|budget|assign|assigned|owner|salesperson|sales person)\b",
        value,
        flags=re.IGNORECASE,
    )[0]
    return clean_query(value)


def clean_record_name_for_doctype(value, doctype):
    if doctype != "Program":
        return clean_record_name(value)
    value = EMAIL_PATTERN.sub("", value or "")
    value = re.sub(r"^\s*(?:named|called|name)\s+", "", value, flags=re.IGNORECASE)
    # "in" and "of" are part of normal academic Program names and must not
    # be treated as field separators (for example, Bachelor's in Accounting).
    value = re.split(
        r"\b(?:with|from|via|using|under|email|worth|valued|value|amount|budget|assign|assigned|owner|salesperson|sales person)\b",
        value,
        flags=re.IGNORECASE,
    )[0]
    return clean_query(value)


def set_first_existing(data, fieldnames, candidates, value):
    fieldname = first_existing_field(candidates, fieldnames)
    if fieldname and value not in (None, ""):
        data[fieldname] = clean_query(value)


def set_first_matching_field(data, fields, matcher, value):
    if value in (None, "", []):
        return
    field = matcher(fields)
    fieldname = (field or {}).get("fieldname")
    if fieldname and fieldname not in data:
        data[fieldname] = value


def amount_field_candidates(fields):
    preferred = ("opportunity_amount", "expected_revenue", "amount", "annual_revenue", "estimated_costing", "budget")
    for fieldname in preferred:
        field = field_by_name(fields, fieldname)
        if field and is_editable_business_field(field) and field.get("fieldtype") in NUMERIC_FIELDTYPES:
            return field
    for field in fields or []:
        text = normalize(f"{field.get('fieldname')} {field_label(field)}")
        if field.get("fieldtype") in NUMERIC_FIELDTYPES and is_editable_business_field(field) and any(token in text for token in ("amount", "value", "revenue", "budget")):
            return field
    return None


def assignment_field_candidates(fields):
    preferred = ("opportunity_owner", "assigned_to", "sales_person", "project_manager", "account_manager")
    for fieldname in preferred:
        field = field_by_name(fields, fieldname)
        if field and is_editable_business_field(field):
            return field
    for field in fields or []:
        text = normalize(f"{field.get('fieldname')} {field_label(field)}")
        if is_editable_business_field(field) and any(token in text for token in ("assigned", "assignee", "sales person", "salesperson", "manager")):
            return field
    return None


def field_by_name(fields, fieldname):
    return next((field for field in fields or [] if field.get("fieldname") == fieldname), None)


def first_existing_field(candidates, fieldnames):
    for fieldname in candidates or []:
        if fieldname in fieldnames:
            return fieldname
    return None


def extract_business_amount(message):
    text = str(message or "")
    patterns = (
        r"\b(?:worth|valued\s+at|value|amount|budget|deal\s+value)\s*(?:of|is|=|:|at)?\s*(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)\s*([A-Za-z]+)?",
        r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*(?:\.\d+)?)\s*([A-Za-z]+)?\s+(?:opportunity|deal)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        number = parse_numeric_value(match.group(1))
        if not isinstance(number, (int, float)):
            continue
        return number * amount_multiplier(match.group(2))
    return None


def amount_multiplier(unit):
    normalized = normalize(unit)
    if normalized in {"lakh", "lakhs", "lac", "lacs"}:
        return 100000
    if normalized in {"crore", "crores"}:
        return 10000000
    if normalized in {"k", "thousand"}:
        return 1000
    if normalized in {"m", "mn", "million"}:
        return 1000000
    return 1


def extract_assignment_value(message):
    text = str(message or "")
    match = re.search(
        r"\b(?:assign(?:ed)?(?:\s+it)?\s+to|owner\s+to|sales\s*person\s+to|salesperson\s+to)\s+([A-Za-z0-9][A-Za-z0-9 .@_-]{1,100})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = re.split(r"\b(?:with|worth|value|amount|budget|for|and then|then)\b", match.group(1), flags=re.IGNORECASE)[0]
    return clean_query(value)


def select_option(field, preferred):
    if not field:
        return None
    options = split_options(field.get("options"))
    for item in preferred or []:
        for option in options:
            if normalize(option) == normalize(item):
                return option
    return None


def first_select_option(field):
    options = split_options(field.get("options"))
    return options[0] if options else None


def split_options(options):
    if not options:
        return []
    if isinstance(options, (list, tuple)):
        return [str(item).strip() for item in options if str(item).strip()]
    return [line.strip() for line in str(options).replace(",", "\n").splitlines() if line.strip()]


def select_supports_value(field, value):
    requested = normalize(value)
    return any(normalize(option) == requested for option in split_options((field or {}).get("options")))


def normalize_metadata_default(value):
    if value in (None, ""):
        return value
    normalized = normalize(value)
    if normalized in {"today", "nowdate", "current date"}:
        return str(date.today())
    if normalized in {"now", "current timestamp", "current datetime"}:
        return str(date.today())
    if normalized in {"__user", "user"}:
        return None
    return value


def choose_default_link_value(field, choices):
    choices = choices or []
    if not choices:
        return None

    label = normalize(f"{(field or {}).get('fieldname')} {(field or {}).get('label')}")
    values = [choice.get("value") or choice.get("label") for choice in choices if choice.get("value") or choice.get("label")]
    if not values:
        return None

    root_values = [value for value in values if normalize(value).startswith("all ")]
    non_root_values = [value for value in values if not normalize(value).startswith("all ")]
    if "parent" in label:
        return root_values[0] if root_values else None

    default_named = next((value for value in values if normalize(value).startswith("default")), None)
    if default_named:
        return default_named
    if root_values and non_root_values:
        return non_root_values[0]
    if root_values and len(values) == 1:
        return root_values[0]
    return None


def root_link_candidates(doctype):
    name = clean_query(doctype)
    if not name:
        return []
    plural = pluralize(name)
    return [f"All {plural}", f"All {name}"]


def pluralize(value):
    if str(value).endswith("y"):
        return f"{str(value)[:-1]}ies"
    if str(value).endswith("s"):
        return str(value)
    return f"{value}s"


def title_from_email(email):
    local_part = str(email or "").split("@", 1)[0]
    words = re.split(r"[._-]+", local_part)
    title = " ".join(word.capitalize() for word in words if word)
    return title or local_part


def parse_field_answer(message, field):
    fieldname = str(field.get("fieldname") or "").lower()
    label = str(field.get("label") or "").lower()
    fieldtype = field.get("fieldtype")

    if fieldname == "requirements" and field.get("options") == "Talisma Curriculum Requirement":
        return parse_curriculum_requirements(message)

    text = clean_answer(message, field)

    if fieldname == "items" or fieldtype == "Table":
        return parse_items_answer(text)

    if "email" in fieldname or "email" in label:
        match = EMAIL_PATTERN.search(message or "")
        return match.group(0).strip() if match else None

    if fieldtype in NUMERIC_FIELDTYPES:
        match = NUMBER_PATTERN.search(text)
        if not match:
            return None
        number = match.group(0).replace(",", "")
        if fieldtype == "Int":
            return int(float(number))
        return float(number)

    if fieldtype == "Check":
        normalized = normalize(text)
        if normalized in {"yes", "y", "true", "1", "enable", "enabled"}:
            return 1
        if normalized in {"no", "n", "false", "0", "disable", "disabled"}:
            return 0
        return None

    return text


def clean_answer(message, field):
    text = str(message or "").strip()
    label = str(field.get("label") or "")
    fieldname = str(field.get("fieldname") or "")
    for prefix in (label, fieldname, fieldname.replace("_", " ")):
        if not prefix:
            continue
        text = re.sub(rf"^\s*{re.escape(prefix)}\s*(?:is|=|:|-)?\s*", "", text, flags=re.IGNORECASE)
    return clean_query(text)


def parse_items_answer(text):
    if not text:
        return None
    rows = []
    parts = re.split(r"\s*(?:,|;|\band\b)\s*", text, flags=re.IGNORECASE)
    for part in parts:
        item_code = extract_item_code(part)
        if not item_code:
            continue
        qty = extract_qty(part)
        rows.append({"item_code": item_code, "qty": qty or 1})
    return rows or None


def parse_curriculum_requirements(text):
    if not text:
        return None
    try:
        submitted = json.loads(str(text))
    except (TypeError, ValueError, json.JSONDecodeError):
        submitted = None
    if isinstance(submitted, list):
        rows = []
        for index, item in enumerate(submitted, start=1):
            if not isinstance(item, dict):
                continue
            requirement_type = item.get("requirement_type") or "Required Course"
            course = clean_query(item.get("course")) if item.get("course") else None
            if not course:
                continue
            requirement_code = clean_query(item.get("requirement_code")) or curriculum_requirement_code(course, index)
            row = {
                "requirement_code": requirement_code,
                "requirement_type": requirement_type,
                "sequence": index,
                "active": 1,
                "minimum_credits": float(item.get("minimum_credits") or 0),
                "minimum_grade": item.get("minimum_grade") or "C",
            }
            if course:
                row["course"] = course
            rows.append(row)
        return rows or None
    courses = [clean_query(item) for item in re.split(r"\s*(?:;|,|\r?\n)\s*", text) if clean_query(item)]
    if not courses:
        return None
    return [
        {
            "requirement_code": curriculum_requirement_code(course, index),
            "requirement_type": "Required Course",
            "course": course,
            "sequence": index,
            "active": 1,
            "minimum_credits": 0,
            "minimum_grade": "C",
        }
        for index, course in enumerate(courses, start=1)
    ]


def curriculum_requirement_code(course, index):
    course_code = re.sub(r"[^A-Z0-9]+", "-", str(course or "").upper()).strip("-")
    return f"REQ-{course_code[:24]}" if course_code else f"REQ-{index:03d}"


def parse_multi_value(value):
    if isinstance(value, list):
        return [clean_query(item) for item in value if clean_query(item)]
    return [clean_query(item) for item in str(value or "").split(",") if clean_query(item)]


def extract_item_code(text):
    match = re.search(r"\b(?:item\s+)?([A-Z0-9][A-Z0-9_-]{2,})\b", text or "", re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_qty(text):
    match = re.search(r"\b(?:qty|quantity|x)\s*[:=]?\s*(\d+(?:\.\d+)?)\b", text or "", re.IGNORECASE)
    if not match:
        match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:qty|quantity|pcs|nos|units)\b", text or "", re.IGNORECASE)
    return float(match.group(1)) if match else None


def match_select_option(field, value):
    requested = normalize(value)
    if not requested:
        return None
    for option in split_options(field.get("options")):
        if normalize(option) == requested:
            return option
    for option in split_options(field.get("options")):
        if requested in normalize(option):
            return option
    return None


def serialize_field(field):
    if not field:
        return None
    return {
        "fieldname": field.get("fieldname"),
        "label": field_label(field),
        "fieldtype": field.get("fieldtype"),
        "options": field.get("options"),
    }


PROGRAM_PATTERN_STOP_WORDS = {
    "a",
    "an",
    "and",
    "associate",
    "associates",
    "bachelor",
    "bachelors",
    "certificate",
    "degree",
    "in",
    "master",
    "masters",
    "of",
    "program",
    "the",
}


def recommend_program_values(program_name, rows):
    """Return deterministic Program suggestions learned from existing records."""
    target = normalize_program_title(program_name)
    rows = list(rows or [])
    exact = next(
        (row for row in rows if normalize_program_title(row.get("program_name") or row.get("name")) == target),
        None,
    )
    if exact:
        return {
            key: exact.get(key)
            for key in (
                "talisma_program_code",
                "program_abbreviation",
                "talisma_degree",
                "talisma_academic_unit",
            )
            if exact.get(key) not in (None, "", [])
        }

    level = program_level(program_name)
    target_tokens = program_subject_tokens(program_name)
    ranked = sorted(
        rows,
        key=lambda row: program_pattern_score(program_name, target_tokens, level, row),
        reverse=True,
    )
    closest = ranked[0] if ranked and program_pattern_score(program_name, target_tokens, level, ranked[0]) > 0 else None
    degree = infer_program_degree(level, target_tokens, rows, closest)
    code = generate_program_code(program_name, degree)
    code = unique_program_code(code, program_name, rows)

    suggestions = {
        "talisma_program_code": code,
        "program_abbreviation": code,
        "talisma_degree": degree,
    }
    closest_unit = next(
        (
            row.get("talisma_academic_unit")
            for row in ranked
            if row.get("talisma_academic_unit")
            and program_pattern_score(program_name, target_tokens, level, row) > 0
        ),
        None,
    )
    if closest_unit:
        suggestions["talisma_academic_unit"] = closest_unit
    return {key: value for key, value in suggestions.items() if value not in (None, "", [])}


def normalize_program_title(value):
    value = re.sub(r"([A-Za-z])['’]s\b", r"\1s", str(value or ""), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def program_level(value):
    title = normalize_program_title(value)
    if title.startswith("associate"):
        return "associate"
    if title.startswith("certificate") or " certification" in f" {title}":
        return "certificate"
    if title.startswith("master"):
        return "master"
    if title.startswith("bachelor"):
        return "bachelor"
    return ""


def program_subject_tokens(value):
    return [
        token
        for token in normalize_program_title(value).split()
        if token not in PROGRAM_PATTERN_STOP_WORDS
    ]


def program_pattern_score(program_name, target_tokens, level, row):
    row_name = row.get("program_name") or row.get("name") or ""
    row_tokens = set(program_subject_tokens(row_name))
    shared = len(set(target_tokens) & row_tokens)
    score = shared * 10
    if level and program_level(row_name) == level:
        score += 4
    if target_tokens and row_tokens and set(target_tokens) == row_tokens:
        score += 20
    return score


def infer_program_degree(level, target_tokens, rows, closest=None):
    subject = set(target_tokens or [])
    if level == "associate":
        same_subject = [
            row for row in rows
            if subject and subject & set(program_subject_tokens(row.get("program_name") or row.get("name")))
            and program_level(row.get("program_name") or row.get("name")) == "associate"
            and row.get("talisma_degree")
        ]
        if same_subject:
            return same_subject[0].get("talisma_degree")
        return most_common_program_degree(rows, "associate") or "Associate of Applied Science"
    if level == "certificate":
        return "Certification"
    if level == "master":
        if {"business", "administration", "management"} & subject:
            return "Master of Business Administration"
        if {"public", "health"}.issubset(subject):
            return "Master of Public Health"
        return most_common_program_degree(rows, "master") or "Master of Science"
    if level == "bachelor":
        if closest and program_level(closest.get("program_name") or closest.get("name")) == "bachelor" and closest.get("talisma_degree"):
            return closest.get("talisma_degree")
        return most_common_program_degree(rows, "bachelor") or "Bachelor of Science"
    if closest and closest.get("talisma_degree"):
        return closest.get("talisma_degree")
    return None


def most_common_program_degree(rows, level):
    counts = {}
    for row in rows or []:
        row_name = row.get("program_name") or row.get("name") or ""
        degree = row.get("talisma_degree")
        if degree and program_level(row_name) == level:
            counts[degree] = counts.get(degree, 0) + 1
    return max(counts, key=counts.get) if counts else None


def generate_program_code(program_name, degree=None):
    tokens = program_subject_tokens(program_name)
    subject_code = "".join(token[0].upper() for token in tokens if token)
    level = program_level(program_name)
    if level == "associate":
        prefix = "AS" if normalize_program_title(degree) == "associate of science" else "AA"
    elif level == "certificate":
        prefix = "C"
    elif level == "master":
        prefix = "M"
    elif level == "bachelor":
        prefix = "B"
    else:
        prefix = ""
    return (prefix + subject_code)[:12] or "PROGRAM"


def unique_program_code(code, program_name, rows):
    used = {
        str(row.get("talisma_program_code") or row.get("program_abbreviation") or "").upper():
        normalize_program_title(row.get("program_name") or row.get("name"))
        for row in rows or []
    }
    candidate = str(code or "PROGRAM").upper()
    if candidate not in used or used[candidate] == normalize_program_title(program_name):
        return candidate
    suffix = 2
    while f"{candidate}{suffix}" in used:
        suffix += 1
    return f"{candidate}{suffix}"


def is_cancel_message(message):
    return normalize(message) in {"cancel", "cancel draft", "stop", "never mind", "nevermind"}


def normalize_field_value(field, value):
    fieldtype = field.get("fieldtype")
    if fieldtype == "Check":
        if isinstance(value, bool):
            return 1 if value else 0
        return 1 if str(value).lower() in ("1", "true", "yes", "on") else 0
    if fieldtype == "Int":
        return parse_numeric_value(value, integer=True)
    if fieldtype in ("Float", "Currency", "Percent"):
        return parse_numeric_value(value)
    return clean_query(value) if isinstance(value, str) else value


def parse_numeric_value(value, integer=False):
    if value in (None, ""):
        return value
    if isinstance(value, bool):
        return int(value) if integer else float(value)
    if isinstance(value, (int, float)):
        return int(value) if integer else float(value)

    match = NUMBER_PATTERN.search(str(value).replace(",", ""))
    if not match:
        return value
    try:
        return int(float(match.group(0))) if integer else float(match.group(0))
    except (TypeError, ValueError):
        return value


def normalize_payload_values(payload, fields):
    field_map = {field.get("fieldname"): field for field in fields or [] if field.get("fieldname")}
    normalized = dict(payload or {})
    for fieldname, field in field_map.items():
        if fieldname not in normalized:
            continue
        if field.get("fieldtype") == "Check" or field.get("fieldtype") in NUMERIC_FIELDTYPES:
            normalized[fieldname] = normalize_field_value(field, normalized[fieldname])
    return normalized


def is_required(field):
    return bool(field.get("reqd") or field.get("mandatory"))


def field_label(field):
    return field.get("label") or str(field.get("fieldname") or "Field").replace("_", " ").title()


def clean_payload(data, fields=None):
    field_map = {field.get("fieldname"): field for field in fields or [] if field.get("fieldname")}
    cleaned = {}
    for key, value in (data or {}).items():
        if value in (None, "", []):
            continue
        field = field_map.get(key)
        if field and not is_editable_business_field(field):
            continue
        if not field and is_system_fieldname(key):
            continue
        cleaned[key] = value
    return cleaned


def clean_query(value):
    return " ".join(str(value or "").strip().strip(".,;:()[]{}\"'").split())


def contains_phrase(text, phrase):
    return re.search(rf"(?<!\w){re.escape(str(phrase or '').lower())}(?!\w)", text) is not None


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


def scrub(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


_SERVICE = None


def get_record_creation_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RecordCreationService()
    return _SERVICE
