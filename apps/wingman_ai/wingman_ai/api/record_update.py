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

from wingman_ai.api.exception_guard import guarded_api_call
from wingman_ai.conversation_recovery import RecoveryDecisionEngine
from wingman_ai.erp_service.validation import is_setup_prerequisite_message
from wingman_ai.execution_verification import ExecutionVerificationEngine
from wingman_ai.business_skills.record_update.formatter import format_post_update_follow_up, format_update_success
from wingman_ai.business_skills.record_update.service import get_record_update_service
from wingman_ai.repositories.conversation_repository import clear_pending_update_draft


@frappe.whitelist()
def update_record(doctype=None, docname=None, data=None, old_values=None, conversation_id=None):
    user = current_user()

    def run():
        require_value("doctype", doctype)
        require_value("docname", docname)

        payload = parse_json(data, {})
        previous_values = parse_json(old_values, {})
        service = get_record_update_service()
        response = service.update_record(doctype=doctype, docname=docname, data=payload, user=user)
        response["message"] = format_update_success(response, doctype, docname)
        if response.get("success"):
            attach_execution_verification(response, service, doctype, docname, payload, user=user)
            if conversation_id:
                clear_pending_update_draft(conversation_id, user=user)
            undo_action = build_undo_action(doctype, docname, previous_values) if previous_values else None
            response["follow_up"] = format_post_update_follow_up(doctype, docname, undo_action=undo_action)
        else:
            response = attach_validation_follow_up(response, service, doctype, docname, payload, user=user)
            strip_operations_center_when_recoverable(response)
        return response

    return guarded_api_call(
        "update",
        run,
        doctype=doctype,
        docname=docname,
        user=user,
        data=parse_json(data, {}) if data else {},
        component="RecordUpdateAPI",
        erpnext_api="wingman_ai.api.record_update.update_record",
    )


@frappe.whitelist()
def continue_update_field(
    doctype=None,
    docname=None,
    fieldname=None,
    value=None,
    current=None,
    changes=None,
    original_message=None,
    conversation_id=None,
):
    user = current_user()

    def run():
        require_value("doctype", doctype)
        require_value("docname", docname)
        require_value("fieldname", fieldname)

        service = get_record_update_service()
        prepared = service.continue_inline_field(
            doctype=doctype,
            docname=docname,
            fieldname=fieldname,
            value=value,
            current=parse_json(current, {}),
            changes=parse_json(changes, {}),
            original_message=original_message,
            conversation_id=conversation_id,
            user=user,
        )
        if conversation_id:
            service.sync_pending_update(prepared, context={"conversation_id": conversation_id, "user": user})

        from wingman_ai.business_skills.record_update.capability import build_actions

        return {
            "success": True,
            "message": prepared.get("message"),
            "result": prepared,
            "follow_up": {"message": prepared.get("message"), "actions": build_actions(prepared)},
        }

    return guarded_api_call(
        "update_session",
        run,
        doctype=doctype,
        docname=docname,
        user=user,
        data={"fieldname": fieldname},
        component="RecordUpdateAPI",
        erpnext_api="wingman_ai.api.record_update.continue_update_field",
    )


def build_undo_action(doctype, docname, old_values):
    return {
        "type": "update",
        "label": "Undo Update",
        "method": "wingman_ai.api.record_update.update_record",
        "payload": {
            "doctype": doctype,
            "docname": docname,
            "data": old_values or {},
        },
        "requires_confirmation": True,
        "auto_execute": False,
        "enabled": bool(old_values),
    }


def attach_execution_verification(response, service, doctype, docname, data, user=None):
    if not response.get("success"):
        return response
    response["execution_verification"] = ExecutionVerificationEngine(service.erp_service).verify_update(
        doctype,
        docname,
        expected_changes=data or {},
        user=user,
    )
    return response


def attach_validation_follow_up(response, service, doctype, docname, data, user=None):
    if response.get("success") or response.get("follow_up") or not response.get("validation_issues"):
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
                    "- The update flow is paused until the site schema is repaired.",
                ]
            ),
            "actions": [],
        }
        return response

    metadata = service.get_metadata(doctype)
    fields = metadata.get("fields") or []
    decision = RecoveryDecisionEngine().decide_validation(
        doctype,
        "write",
        issues=response.get("validation_issues") or [],
        fields=fields,
        response=response,
    )
    if not decision.get("recoverable"):
        response["recovery_decision"] = decision
        return response

    read_response = service.erp_service.read_document(doctype, docname, user=user)
    if not read_response.get("success"):
        return response

    prepared = service.build_prepared_update(
        doctype,
        docname,
        read_response.get("result") or {},
        fields,
        data or {},
        user=user,
    )
    if prepared.get("ready"):
        return response

    from wingman_ai.business_skills.record_update.capability import build_actions

    response["message"] = f"Talisma OneCampus needs one more detail before updating {doctype}."
    response["result"] = prepared
    response["follow_up"] = {"message": prepared.get("message"), "actions": build_actions(prepared)}
    return response


def first_setup_prerequisite(issues):
    for issue in issues or []:
        message = (issue or {}).get("message") if isinstance(issue, dict) else getattr(issue, "message", None)
        if message and is_setup_prerequisite_message(message):
            return message
    return None


def strip_operations_center_when_recoverable(response):
    if response.get("success") is True or not isinstance(response.get("follow_up"), dict):
        return response
    response["recoverable_follow_up"] = True
    response.pop("exception_diagnostic", None)
    actions = response.get("actions")
    if isinstance(actions, list) and all((action or {}).get("action_center") for action in actions):
        response.pop("actions", None)
    return response


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
