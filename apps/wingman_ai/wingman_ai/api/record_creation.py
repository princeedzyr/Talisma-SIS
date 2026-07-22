import json

try:
    import frappe
except ImportError:
    class _FrappeStub:
        @staticmethod
        def whitelist():
            def decorator(fn):
                return fn

            return decorator

    frappe = _FrappeStub()

from wingman_ai.business_skills.record_creation.service import get_record_creation_service
from wingman_ai.business_skills.record_creation.formatter import format_field_retry
from wingman_ai.api.exception_guard import guarded_api_call
from wingman_ai.conversation_recovery import RecoveryDecisionEngine
from wingman_ai.erp_service.validation import is_setup_prerequisite_message
from wingman_ai.execution_verification import ExecutionVerificationEngine
from wingman_ai.post_creation import PostCreationWorkflowEngine
from wingman_ai.review_builder.workflow import build_dependency_session_payload


@frappe.whitelist()
def create_record(doctype=None, data=None, source_message=None, resume_action=None, dependency_context=None):
    user = current_user()
    def run():
        service = get_record_creation_service()
        parsed_resume_action = parse_json(resume_action, None)
        local_doctype = doctype
        local_data = data
        if source_message:
            prepared = service.prepare_create_from_message(str(source_message), context={"user": user})
            if not prepared.get("supported") or not prepared.get("ready"):
                return {
                    "success": False,
                    "message": prepared.get("message") or "The dependency record is not ready to create.",
                    "result": prepared,
                    "errors": [{"code": "dependency_not_ready", "message": "The dependency record is not ready to create."}],
                    "validation_issues": [],
                }
            local_doctype = prepared.get("doctype")
            local_data = prepared.get("data") or {}
        else:
            require_value("doctype", local_doctype)
            local_data = parse_json(local_data, {})

        reset_captured_messages()
        response = service.create_record(doctype=local_doctype, data=local_data, user=user)
        server_messages = collect_captured_messages()
        if server_messages:
            response["server_messages"] = server_messages
        response = attach_dependency_follow_up(response, service, local_doctype, local_data, parsed_resume_action, user=user)
        response = attach_validation_follow_up(response, service, local_doctype, local_data, user=user)
        response = attach_post_creation_follow_up(response, service, local_doctype, messages=server_messages, user=user)
        attach_execution_verification(response, service, local_doctype, local_data, user=user)
        strip_operations_center_when_recoverable(response)
        if response.get("success") and parsed_resume_action:
            response["resume_action"] = parsed_resume_action
        return response

    return guarded_api_call(
        "create",
        run,
        doctype=doctype,
        user=user,
        data=parse_json(data, {}) if data else {},
        source_message=source_message,
        resume_action=parse_json(resume_action, None),
        dependency_context=parse_json(dependency_context, None),
        component="RecordCreationAPI",
        erpnext_api="wingman_ai.api.record_creation.create_record",
    )


@frappe.whitelist()
def continue_dependency_create(doctype=None, data=None, fieldname=None, value=None, resume_review=None):
    user = current_user()
    def run():
        service = get_record_creation_service()
        require_value("doctype", doctype)
        require_value("fieldname", fieldname)

        payload = parse_json(data, {})
        parsed_resume_review = parse_json(resume_review, None)
        metadata = service.get_metadata(doctype)
        fields = metadata.get("fields") or []
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
        field = field_map.get(fieldname)
        if not field:
            return {
                "success": False,
                "message": f"{fieldname} is not available on {doctype}.",
                "errors": [{"code": "field_not_found", "message": f"{fieldname} is not available on {doctype}."}],
                "validation_issues": [],
            }

        parsed = service.parse_answer_for_field(value, field, user=user)
        if not parsed.get("accepted"):
            prepared = service.build_prepared_create(doctype, payload, fields, context={"user": user}, user=user)
            prepared["next_missing_field"] = service.creation_session.serialize_field(field, user=user)
            prepared["message"] = format_field_retry(prepared, field, reason=parsed.get("message"))
            return {
                "success": False,
                "message": prepared["message"],
                "result": prepared,
                "errors": [{"code": "invalid_field_value", "message": parsed.get("message") or f"{fieldname} is invalid."}],
                "validation_issues": [],
            }

        payload[fieldname] = parsed.get("value")
        prepared = service.build_prepared_create(doctype, payload, fields, context={"user": user}, user=user)
        return {
            "success": True,
            "message": f"Captured {field.get('label') or fieldname}.",
            "result": prepared,
            "follow_up": build_dependency_session_payload(prepared, resume_review=parsed_resume_review),
        }

    return guarded_api_call(
        "dependency_resolution",
        run,
        doctype=doctype,
        user=user,
        data=parse_json(data, {}) if data else {},
        component="RecordCreationAPI",
        erpnext_api="wingman_ai.api.record_creation.continue_dependency_create",
    )


def attach_dependency_follow_up(response, service, doctype, data, resume_action=None, user=None):
    if response.get("success"):
        return response
    dependencies = service.dependency_service.detect_from_validation_response(doctype, data or {}, response, user=user)
    if dependencies:
        dependencies = service.add_dependency_reviews(dependencies, user=user)
        parent_action = resume_action or {
            "type": "create",
            "label": f"Create {doctype}",
            "method": "wingman_ai.api.record_creation.create_record",
            "payload": {"doctype": doctype, "data": data or {}},
            "requires_confirmation": True,
            "auto_execute": False,
            "enabled": True,
        }
        response["follow_up"] = service.dependency_service.build_follow_up(doctype, dependencies, resume_action=parent_action)
    return response


def attach_validation_follow_up(response, service, doctype, data, user=None):
    if response.get("success") or response.get("follow_up"):
        return response
    if not response.get("validation_issues"):
        return response

    setup_message = first_setup_prerequisite(response.get("validation_issues"))
    if setup_message:
        response["message"] = "Talisma OneCampus setup prerequisite is missing."
        response["follow_up"] = {
            "message": "\n".join(
                [
                    "Setup Prerequisite",
                    setup_message,
                    "",
                    "Current Status",
                    "- No Talisma OneCampus data was changed.",
                    "- The create flow is paused until the site schema is repaired.",
                    "",
                    "What You Can Do Next",
                    "- Run bench migrate for the site.",
                    "- Clear cache and reload Desk.",
                    "- Try the create request again after migration completes.",
                ]
            ),
            "actions": [],
        }
        return response

    metadata = service.get_metadata(doctype)
    fields = metadata.get("fields") or []
    decision = RecoveryDecisionEngine().decide_validation(
        doctype,
        "create",
        issues=response.get("validation_issues") or [],
        fields=fields,
        response=response,
    )
    if not decision.get("recoverable"):
        response["message"] = "Talisma OneCampus needs administrator attention before this can continue."
        response["recovery_decision"] = decision
        return response

    prepared = service.build_prepared_create(doctype, data or {}, fields, context={"user": user}, user=user)
    if prepared.get("ready"):
        return response

    response["message"] = f"Talisma OneCampus needs one more detail before creating {doctype}."
    response["result"] = prepared
    response["follow_up"] = build_dependency_session_payload(prepared)
    return response


def first_setup_prerequisite(issues):
    for issue in issues or []:
        message = (issue or {}).get("message") if isinstance(issue, dict) else getattr(issue, "message", None)
        if message and is_setup_prerequisite_message(message):
            return message
    return None


def attach_post_creation_follow_up(response, service, doctype, messages=None, user=None):
    if not response.get("success"):
        return response
    follow_up = PostCreationWorkflowEngine(service.erp_service).build_follow_up(
        doctype,
        result=response.get("result") or {},
        response=response,
        messages=messages or response.get("server_messages") or [],
        user=user,
    )
    if follow_up:
        response["follow_up"] = follow_up
    return response


def strip_operations_center_when_recoverable(response):
    if response.get("success") is True or not isinstance(response.get("follow_up"), dict):
        return response
    response["recoverable_follow_up"] = True
    response.pop("exception_diagnostic", None)
    actions = response.get("actions")
    if isinstance(actions, list) and all((action or {}).get("action_center") for action in actions):
        response.pop("actions", None)
    return response


def attach_execution_verification(response, service, doctype, data, user=None):
    if not response.get("success"):
        return response
    response["execution_verification"] = ExecutionVerificationEngine(service.erp_service).verify_create(
        doctype,
        response=response,
        expected_data=data or {},
        user=user,
    )
    return response


def reset_captured_messages():
    local = getattr(frappe, "local", None)
    if local is not None and hasattr(local, "message_log"):
        local.message_log = []


def collect_captured_messages():
    local = getattr(frappe, "local", None)
    raw_messages = getattr(local, "message_log", []) if local is not None else []
    messages = [extract_message(item) for item in raw_messages or []]
    messages = [message for message in messages if message]
    if messages and local is not None and hasattr(local, "message_log"):
        local.message_log = []
    return messages


def extract_message(item):
    if isinstance(item, dict):
        return item.get("message") or item.get("title")
    if isinstance(item, str):
        parsed = parse_json(item, None)
        if isinstance(parsed, dict):
            return parsed.get("message") or parsed.get("title")
        return item
    return str(item) if item else None


def current_user():
    return getattr(getattr(frappe, "session", None), "user", None)


def require_value(label, value):
    if value:
        return
    try:
        frappe.throw(f"{label} is required.")
    except AttributeError:
        raise ValueError(f"{label} is required.")


def parse_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
