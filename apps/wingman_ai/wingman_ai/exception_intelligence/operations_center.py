from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from wingman_ai.exception_intelligence.action_center import ActionCenterService
from wingman_ai.repositories.conversation_repository import end_conversation, get_conversation_state, set_conversation_state


_DIAGNOSTICS = {}
_INCIDENTS = {}
_DRAFTS = {}


class OperationsCenter:
    def __init__(self, action_center=None):
        self.action_center = action_center or ActionCenterService()

    def register_diagnostic(self, diagnostic):
        diagnostic = deepcopy(diagnostic or {})
        diagnostic_id = diagnostic.get("diagnostic_id") or f"EIF-{uuid4().hex[:10].upper()}"
        diagnostic["diagnostic_id"] = diagnostic_id
        _DIAGNOSTICS[diagnostic_id] = diagnostic
        return deepcopy(diagnostic)

    def get_diagnostic(self, diagnostic_id):
        return deepcopy(_DIAGNOSTICS.get(diagnostic_id) or {})

    def build_actions(self, diagnostic, retry_state=None):
        diagnostic = diagnostic or {}
        retry_state = retry_state or {}
        diagnostic_id = diagnostic.get("diagnostic_id")
        preserved_session = diagnostic.get("preserved_session") or {}
        can_retry = retry_state.get("can_retry_now", False)
        role_profile = diagnostic.get("role_profile") or (preserved_session.get("role_profile") if isinstance(preserved_session, dict) else None)

        actions = []
        actions.extend(self.build_recovery_actions(diagnostic))
        actions.extend(
            [
            server_action(
                "retry",
                "Retry",
                "wingman_ai.api.exception_intelligence.retry_operation",
                {"diagnostic_id": diagnostic_id, "preserved_session": preserved_session},
                requires_confirmation=True,
                enabled=True,
                description="Retry the failed operation from the preserved step." if can_retry else "Retry will use the preserved session when the blocking issue is fixed.",
            ),
            server_action(
                "notify_administrator",
                "Notify Administrator",
                "wingman_ai.api.exception_intelligence.notify_administrator",
                {"diagnostic_id": diagnostic_id},
                description="Create a structured incident for the responsible team.",
            ),
            server_action(
                "save_draft",
                "Save Draft",
                "wingman_ai.api.exception_intelligence.save_draft",
                {"diagnostic_id": diagnostic_id, "preserved_session": preserved_session},
                description="Save the collected values and recovery state.",
            ),
            server_action(
                "resume_later",
                "Resume Later",
                "wingman_ai.api.exception_intelligence.save_draft",
                {"diagnostic_id": diagnostic_id, "preserved_session": preserved_session, "resume_later": True},
                description="Save the session so the user can return later.",
            ),
            server_action(
                "copy_diagnostic",
                "Copy Diagnostic",
                "wingman_ai.api.exception_intelligence.copy_diagnostic",
                {"diagnostic_id": diagnostic_id},
                description="Return a shareable diagnostic summary.",
            ),
            server_action(
                "cancel_operation",
                "Cancel",
                "wingman_ai.api.exception_intelligence.cancel_operation",
                {"diagnostic_id": diagnostic_id},
                requires_confirmation=True,
                description="Cancel the paused operation without changing Talisma OneCampus data.",
            ),
            ]
        )
        if role_profile in {"administrator", "developer"}:
            actions.append(
                server_action(
                    "view_technical_details",
                    "View Technical Details",
                    "wingman_ai.api.exception_intelligence.view_technical_details",
                    {"diagnostic_id": diagnostic_id},
                    description="Show role-aware technical details.",
                )
            )
        return self.action_center.build(diagnostic, dedupe_actions(actions), retry_state=retry_state)

    def build_recovery_actions(self, diagnostic):
        actions = []
        actions.extend(self.build_dependency_recovery_actions(diagnostic))
        actions.extend(self.build_field_correction_actions(diagnostic))
        return actions

    def build_dependency_recovery_actions(self, diagnostic):
        dependencies = dependency_candidates_from_diagnostic(diagnostic)
        if not dependencies:
            return []

        try:
            from wingman_ai.business_skills.record_creation.service import get_record_creation_service
            from wingman_ai.review_builder.workflow import build_dependency_review_actions

            service = get_record_creation_service()
            dependencies = service.add_dependency_reviews(dependencies, user=(diagnostic.get("preserved_session") or {}).get("user"))
            resume_review = resume_review_from_diagnostic(diagnostic)
            resume_action = resume_action_from_diagnostic(diagnostic)
            actions = []
            for dependency in dependencies:
                for action in build_dependency_review_actions([dependency], resume_review=resume_review):
                    action = normalize_dependency_action_label(action, dependency)
                    attach_resume_action(action, resume_action)
                    action["description"] = dependency_action_description(action, dependency)
                    actions.append(action)
                edit_action = build_dependency_edit_value_action(dependency, resume_review=resume_review)
                if edit_action:
                    attach_resume_action(edit_action, resume_action)
                    actions.append(edit_action)
            return actions or fallback_dependency_actions(dependencies, diagnostic)
        except Exception:
            return fallback_dependency_actions(dependencies, diagnostic)

    def build_field_correction_actions(self, diagnostic):
        preserved = diagnostic.get("preserved_session") or {}
        doctype = preserved.get("doctype") or diagnostic.get("target_doctype")
        data = preserved.get("collected_fields") or {}
        operation = str(preserved.get("operation") or diagnostic.get("crud_action") or "").lower()
        if not doctype or not operation.startswith("create"):
            return []

        try:
            from wingman_ai.creation_session.service import CreationSessionManager
            from wingman_ai.erp_service import get_erp_service
            from wingman_ai.field_filters import is_editable_business_field
            from wingman_ai.review_builder.workflow import build_collect_field_action

            service = get_erp_service()
            response = service.get_metadata(doctype)
            metadata = response.get("result") if isinstance(response, dict) else response
            fields = (metadata or {}).get("fields") or []
            field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
            actions = []
            for issue in preserved.get("validation_state") or []:
                fieldname = issue.get("fieldname") if isinstance(issue, dict) else None
                field = field_map.get(fieldname)
                if not field or not is_editable_business_field(field):
                    continue
                serialized = CreationSessionManager(service).serialize_field(field, user=preserved.get("user"))
                action = build_collect_field_action(
                    serialized,
                    method="wingman_ai.api.record_creation.continue_dependency_create",
                    args={
                        "doctype": doctype,
                        "data": data,
                        "fieldname": fieldname,
                        "resume_review": resume_review_from_diagnostic(diagnostic),
                    },
                    action_type="validation_correction",
                )
                action["label"] = f"Edit {serialized.get('label') or fieldname}"
                action["description"] = "Reopen this field so the saved workflow can continue with the corrected value."
                action["action_kind"] = "edit_value" if issue.get("issue_type") == "linked_document" else "validation_correction"
                actions.append(action)
            return actions
        except Exception:
            return []

    def save_draft(self, diagnostic_id=None, preserved_session=None, resume_later=False, user=None):
        diagnostic = self.get_diagnostic(diagnostic_id)
        session = deepcopy(preserved_session or diagnostic.get("preserved_session") or {})
        draft_id = f"EIF-DRAFT-{uuid4().hex[:10].upper()}"
        draft = {
            "draft_id": draft_id,
            "diagnostic_id": diagnostic_id,
            "preserved_session": session,
            "resume_later": bool(resume_later),
            "user": user,
            "status": "saved",
            "created_at": utc_now(),
        }
        _DRAFTS[draft_id] = deepcopy(draft)
        conversation_id = session.get("conversation_id")
        if conversation_id:
            existing_state = get_conversation_state(conversation_id, user=user) or {}
            existing_state["exception_saved_draft"] = draft
            set_conversation_state(conversation_id, existing_state, user=user)
        return draft

    def notify_administrator(self, diagnostic_id=None, user=None):
        diagnostic = self.get_diagnostic(diagnostic_id)
        incident_id = f"EIF-INC-{uuid4().hex[:10].upper()}"
        incident = {
            "incident_id": incident_id,
            "diagnostic_id": diagnostic_id,
            "operation": diagnostic.get("operation"),
            "doctype": diagnostic.get("target_doctype"),
            "timestamp": utc_now(),
            "user": user or (diagnostic.get("preserved_session") or {}).get("user"),
            "conversation_id": diagnostic.get("conversation_id") or (diagnostic.get("preserved_session") or {}).get("conversation_id"),
            "root_cause": diagnostic.get("root_cause"),
            "severity": diagnostic.get("severity"),
            "recommended_resolution": diagnostic.get("recommended_resolution"),
            "responsible_team": diagnostic.get("responsible_team"),
            "status": "open",
        }
        _INCIDENTS[incident_id] = deepcopy(incident)
        return incident

    def copy_diagnostic(self, diagnostic_id=None):
        diagnostic = self.get_diagnostic(diagnostic_id)
        return {
            "diagnostic_id": diagnostic_id,
            "summary": {
                "issue_type": diagnostic.get("issue_type"),
                "severity": diagnostic.get("severity"),
                "operation": diagnostic.get("operation"),
                "doctype": diagnostic.get("target_doctype"),
                "root_cause": diagnostic.get("root_cause"),
                "responsible_team": diagnostic.get("responsible_team"),
                "recommended_resolution": diagnostic.get("recommended_resolution"),
            },
        }

    def technical_details(self, diagnostic_id=None, role_profile=None):
        diagnostic = self.get_diagnostic(diagnostic_id)
        role_profile = role_profile or "business_user"
        details = {
            "diagnostic_id": diagnostic_id,
            "framework_component": diagnostic.get("framework_component"),
            "failure_stage": diagnostic.get("failure_stage"),
            "trace_id": (diagnostic.get("technical_reference") or {}).get("trace_id"),
            "category": diagnostic.get("category"),
            "recovery_strategy": diagnostic.get("recovery_strategy"),
        }
        if role_profile in {"administrator", "developer"}:
            details["technical_reference"] = diagnostic.get("technical_reference") or {}
            details["preserved_session"] = diagnostic.get("preserved_session") or {}
        return details

    def cancel_operation(self, diagnostic_id=None, user=None):
        diagnostic = self.get_diagnostic(diagnostic_id)
        conversation_id = diagnostic.get("conversation_id") or (diagnostic.get("preserved_session") or {}).get("conversation_id")
        if conversation_id:
            end_conversation(conversation_id, user=user)
        return {
            "diagnostic_id": diagnostic_id,
            "status": "cancelled",
            "message": "The paused operation was cancelled. No Talisma OneCampus data was changed.",
        }


def server_action(action_type, label, method, payload=None, requires_confirmation=False, enabled=True, description=None):
    action = {
        "type": action_type,
        "label": label,
        "method": method,
        "payload": payload or {},
        "requires_confirmation": bool(requires_confirmation),
        "auto_execute": False,
        "enabled": bool(enabled),
    }
    if description:
        action["description"] = description
    return action


def mark_action_center(actions):
    result = []
    for action in actions or []:
        item = deepcopy(action or {})
        item["action_center"] = True
        item.setdefault("presentation", {})["section"] = "action_center"
        result.append(item)
    return result


def dedupe_actions(actions):
    seen = set()
    result = []
    for action in actions or []:
        key = (
            action.get("type"),
            action.get("label"),
            action.get("method"),
            stable_payload_key(action.get("payload")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(action)
    return result


def stable_payload_key(payload):
    if not isinstance(payload, dict):
        return str(payload)
    important = {
        key: payload.get(key)
        for key in ("diagnostic_id", "doctype", "docname", "fieldname", "value")
        if payload.get(key) not in (None, "", [], {})
    }
    data = payload.get("data")
    if isinstance(data, dict):
        important["data"] = tuple(sorted((str(key), str(value)) for key, value in data.items()))
    return tuple(sorted((str(key), str(value)) for key, value in important.items()))


def dependency_candidates_from_diagnostic(diagnostic):
    preserved = diagnostic.get("preserved_session") or {}
    doctype = preserved.get("doctype") or diagnostic.get("target_doctype")
    data = dict(preserved.get("collected_fields") or {})
    user = preserved.get("user")
    if not doctype:
        return []

    validation_issues = [
        dict(issue)
        for issue in preserved.get("validation_state") or []
        if isinstance(issue, dict)
    ]
    dependencies = []

    try:
        from wingman_ai.dependency_resolution.service import DependencyResolutionService

        resolver = DependencyResolutionService()
        if validation_issues:
            dependencies.extend(
                resolver.detect_from_validation_response(
                    doctype,
                    data,
                    {"validation_issues": validation_issues},
                    user=user,
                )
            )
        if not dependencies:
            dependencies.extend(
                resolver.detect_for_operation(
                    doctype,
                    data,
                    operation=preserved.get("operation") or diagnostic.get("crud_action") or "create",
                    docname=preserved.get("docname") or diagnostic.get("docname"),
                    user=user,
                )
            )
    except Exception:
        dependencies.extend(fallback_dependencies_from_validation(doctype, data, validation_issues))

    if not dependencies and validation_issues:
        dependencies.extend(fallback_dependencies_from_validation(doctype, data, validation_issues))
    if not dependencies:
        dependencies.extend(normalize_preserved_dependencies(preserved.get("dependencies"), doctype, data))
    return dedupe_dependencies(dependencies)


def fallback_dependencies_from_validation(source_doctype, source_data, validation_issues):
    dependencies = []
    for issue in validation_issues or []:
        if issue.get("issue_type") != "linked_document":
            continue
        fieldname = issue.get("fieldname")
        target_doctype = parse_target_doctype(issue.get("message"))
        value = (source_data or {}).get(fieldname)
        if not fieldname or not target_doctype or value in (None, "", []):
            continue
        dependencies.append(
            {
                "fieldname": fieldname,
                "label": labelize(fieldname),
                "target_doctype": target_doctype,
                "value": value,
                "create_data": {},
                "matches": [],
                "source_doctype": source_doctype,
                "source_data": dict(source_data or {}),
                "source_message": f"Create {target_doctype} {value}",
                "issue": dict(issue),
            }
        )
    return dependencies


def normalize_preserved_dependencies(items, source_doctype, source_data):
    dependencies = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        fieldname = item.get("fieldname")
        target_doctype = item.get("target_doctype") or item.get("doctype")
        value = item.get("value") or (source_data or {}).get(fieldname)
        if not target_doctype or value in (None, "", []):
            continue
        normalized = dict(item)
        normalized.setdefault("source_doctype", source_doctype)
        normalized.setdefault("source_data", dict(source_data or {}))
        normalized.setdefault("source_message", f"Create {target_doctype} {value}")
        normalized.setdefault("label", labelize(fieldname or target_doctype))
        normalized.setdefault("target_doctype", target_doctype)
        normalized.setdefault("value", value)
        dependencies.append(normalized)
    return dependencies


def dedupe_dependencies(dependencies):
    result = []
    seen = set()
    for dependency in dependencies or []:
        key = (dependency.get("fieldname"), dependency.get("target_doctype"), str(dependency.get("value")))
        if key in seen:
            continue
        seen.add(key)
        result.append(dependency)
    return result


def normalize_dependency_action_label(action, dependency):
    item = deepcopy(action or {})
    target_doctype = dependency.get("target_doctype") or "Record"
    value = dependency.get("value")
    if item.get("type") == "review_dependency":
        item["label"] = f"Create {target_doctype} {value}".strip()
        item["action_kind"] = "create_missing_record"
    elif item.get("type") == "collect_field":
        item["label"] = f"Choose Existing {target_doctype}".strip()
        item["action_kind"] = "choose_existing_record"
    return item


def dependency_action_description(action, dependency):
    target_doctype = dependency.get("target_doctype") or "record"
    value = dependency.get("value")
    if action.get("action_kind") == "create_missing_record":
        return f"Create the missing {target_doctype} record and resume the saved workflow."
    if action.get("action_kind") == "choose_existing_record":
        return f"Search readable {target_doctype} records and bind the selected value to this workflow."
    return f"Resolve {target_doctype} {value} and continue."


def build_dependency_edit_value_action(dependency, resume_review=None):
    source_doctype = dependency.get("source_doctype")
    fieldname = dependency.get("fieldname")
    target_doctype = dependency.get("target_doctype")
    if not source_doctype or not fieldname:
        return None

    try:
        from wingman_ai.creation_session.service import CreationSessionManager
        from wingman_ai.erp_service import get_erp_service
        from wingman_ai.field_filters import is_editable_business_field
        from wingman_ai.review_builder.workflow import build_collect_field_action

        erp_service = get_erp_service()
        response = erp_service.get_metadata(source_doctype)
        metadata = response.get("result") if isinstance(response, dict) else response
        fields = (metadata or {}).get("fields") or []
        field = next((item for item in fields if item.get("fieldname") == fieldname), None)
        if not field or not is_editable_business_field(field):
            return None

        serialized = CreationSessionManager(erp_service).serialize_field(field, user=dependency.get("user"))
        serialized["required"] = True
        if target_doctype and serialized.get("fieldtype") == "Link":
            serialized["options"] = target_doctype
            serialized.setdefault("component", {})["target_doctype"] = target_doctype
            serialized["component"]["allow_create"] = True
        args = {
            "doctype": source_doctype,
            "data": dependency.get("source_data") or {},
            "fieldname": fieldname,
        }
        if resume_review:
            args["resume_review"] = resume_review
        action = build_collect_field_action(
            serialized,
            method="wingman_ai.api.record_creation.continue_dependency_create",
            args=args,
            action_type="field_correction",
        )
        action["label"] = f"Edit {serialized.get('label') or fieldname}"
        action["description"] = "Change the value inline and continue validation from the preserved workflow."
        action["action_kind"] = "edit_value"
        return action
    except Exception:
        return None


def attach_resume_action(action, resume_action):
    if not action or not resume_action:
        return action
    if action.get("type") == "create":
        action.setdefault("payload", {})["resume_action"] = resume_action
        action["payload"]["auto_resume_parent"] = True
    payload = action.get("payload")
    if isinstance(payload, dict):
        if action.get("type") == "collect_field":
            payload.setdefault("args", {})["resume_review"] = resume_review_payload_from_action(resume_action)
        for child in payload.get("actions") or []:
            attach_resume_action(child, resume_action)
    return action


def resume_review_payload_from_action(resume_action):
    payload = (resume_action or {}).get("payload") or {}
    doctype = payload.get("doctype") or "record"
    data = payload.get("data") or {}
    docname = payload.get("docname")
    if docname:
        return {"message": f"Review {doctype} {docname}"}
    label = next((str(value) for value in data.values() if value not in (None, "", [], {})), "")
    return {"message": f"Create {doctype} {label}".strip()}


def resume_review_from_diagnostic(diagnostic):
    preserved = diagnostic.get("preserved_session") or {}
    message = str(preserved.get("user_input") or "").strip()
    if message:
        return {"message": message}
    action = resume_action_from_diagnostic(diagnostic)
    return resume_review_payload_from_action(action) if action else None


def resume_action_from_diagnostic(diagnostic):
    preserved = diagnostic.get("preserved_session") or {}
    operation = str(preserved.get("operation") or diagnostic.get("crud_action") or "").lower()
    doctype = preserved.get("doctype") or diagnostic.get("target_doctype")
    docname = preserved.get("docname") or diagnostic.get("docname")
    data = preserved.get("collected_fields") or {}
    if not doctype:
        return None
    if operation.startswith("create"):
        return {
            "type": "create",
            "label": f"Create {doctype}",
            "method": "wingman_ai.api.record_creation.create_record",
            "payload": {"doctype": doctype, "data": data},
            "requires_confirmation": True,
            "auto_execute": False,
            "enabled": True,
        }
    if operation.startswith("update") or operation == "write":
        if not docname:
            return None
        return {
            "type": "update",
            "label": f"Update {doctype}",
            "method": "wingman_ai.api.record_update.update_record",
            "payload": {"doctype": doctype, "docname": docname, "data": data},
            "requires_confirmation": True,
            "auto_execute": False,
            "enabled": True,
        }
    if operation.startswith("delete"):
        if not docname:
            return None
        return {
            "type": "delete",
            "label": f"Delete {doctype}",
            "method": "wingman_ai.api.record_delete.delete_record",
            "payload": {"doctype": doctype, "docname": docname},
            "requires_confirmation": True,
            "auto_execute": False,
            "enabled": True,
        }
    return None


def fallback_dependency_actions(dependencies, diagnostic):
    actions = []
    resume_action = resume_action_from_diagnostic(diagnostic)
    resume_review = resume_review_from_diagnostic(diagnostic)
    for dependency in dependencies or []:
        target_doctype = dependency.get("target_doctype")
        value = dependency.get("value")
        if not target_doctype or value in (None, "", []):
            continue
        actions.append(
            {
                "type": "send_message",
                "label": f"Create {target_doctype} {value}".strip(),
                "payload": {"message": f"Create {target_doctype} {value}"},
                "requires_confirmation": False,
                "auto_execute": False,
                "enabled": True,
                "description": f"Start the creation workflow for the missing {target_doctype}.",
                "action_kind": "create_missing_record",
            }
        )
        if resume_action:
            actions[-1]["payload"]["resume_action"] = resume_action
        fieldname = dependency.get("fieldname")
        source_doctype = dependency.get("source_doctype")
        if fieldname and source_doctype:
            field_payload = {
                "fieldname": fieldname,
                "label": dependency.get("label") or target_doctype,
                "fieldtype": "Link",
                "options": target_doctype,
                "component": {
                    "type": "link",
                    "target_doctype": target_doctype,
                    "search_method": "wingman_ai.api.link_resolution.search",
                    "allow_create": True,
                },
                "choices": dependency.get("matches") or [],
                "placeholder": f"Search or enter {target_doctype}",
                "required": True,
            }
            action_args = {
                "doctype": source_doctype,
                "data": dependency.get("source_data") or {},
                "fieldname": fieldname,
                "resume_review": resume_review,
            }
            actions.append(
                {
                    "type": "collect_field",
                    "label": f"Choose Existing {target_doctype}".strip(),
                    "payload": {
                        "field": field_payload,
                        "method": "wingman_ai.api.record_creation.continue_dependency_create",
                        "action_type": "link_resolution",
                        "args": action_args,
                    },
                    "requires_confirmation": False,
                    "auto_execute": False,
                    "enabled": True,
                    "description": f"Search readable {target_doctype} records and bind one to the saved workflow.",
                    "action_kind": "choose_existing_record",
                }
            )
            actions.append(
                {
                    "type": "collect_field",
                    "label": f"Edit {dependency.get('label') or target_doctype}".strip(),
                    "payload": {
                        "field": {**field_payload, "choices": []},
                        "method": "wingman_ai.api.record_creation.continue_dependency_create",
                        "action_type": "field_correction",
                        "args": action_args,
                    },
                    "requires_confirmation": False,
                    "auto_execute": False,
                    "enabled": True,
                    "description": "Change the value inline and continue validation from the preserved workflow.",
                    "action_kind": "edit_value",
                }
            )
    return actions


def parse_target_doctype(message):
    text = str(message or "")
    lowered = text.lower()
    for marker in (" references a ", " references an "):
        index = lowered.find(marker)
        if index < 0:
            continue
        after = text[index + len(marker):]
        target = after.split(" record", 1)[0]
        return " ".join(target.strip(" .,:;").split()).title()
    return None


def labelize(value):
    return " ".join(str(value or "Field").replace("_", " ").split()).title()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


_OPERATIONS_CENTER = None


def get_operations_center():
    global _OPERATIONS_CENTER
    if _OPERATIONS_CENTER is None:
        _OPERATIONS_CENTER = OperationsCenter()
    return _OPERATIONS_CENTER
