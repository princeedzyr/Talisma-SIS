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

from wingman_ai.exception_intelligence import get_exception_interceptor
from wingman_ai.exception_intelligence.operations_center import get_operations_center
from wingman_ai.exception_intelligence.reporting import ExceptionIntelligenceReporter


@frappe.whitelist()
def diagnose_failure(message=None, operation=None, doctype=None, docname=None, conversation_id=None):
    return get_exception_interceptor().failure_response(
        Exception(message or "Unexpected Talisma OneCampus operation failure."),
        context={
            "operation": operation,
            "doctype": doctype,
            "docname": docname,
            "conversation_id": conversation_id,
            "failure_stage": "Manual diagnosis",
            "component": "ExceptionIntelligenceAPI",
            "erpnext_api": "wingman_ai.api.exception_intelligence.diagnose_failure",
        },
    )


@frappe.whitelist()
def summarize_report(diagnostics=None):
    return ExceptionIntelligenceReporter().summarize(parse_json(diagnostics, []))


@frappe.whitelist()
def retry_operation(diagnostic_id=None, preserved_session=None):
    session = parse_json(preserved_session, {}) or get_operations_center().get_diagnostic(diagnostic_id).get("preserved_session") or {}
    operation = str(session.get("operation") or "").lower()
    doctype = session.get("doctype")
    docname = session.get("docname")
    data = session.get("collected_fields") or {}

    if not doctype:
        return operation_center_response(
            False,
            "Retry could not start because the saved session does not include a DocType.",
            diagnostic_id=diagnostic_id,
        )

    if operation.startswith("create"):
        from wingman_ai.api.record_creation import create_record

        return create_record(doctype=doctype, data=data)

    if operation.startswith("update") or operation == "write":
        if not docname:
            return operation_center_response(False, "Retry could not start because the saved session does not include a record name.", diagnostic_id=diagnostic_id)
        from wingman_ai.api.record_update import update_record

        return update_record(doctype=doctype, docname=docname, data=data)

    if operation.startswith("delete"):
        if not docname:
            return operation_center_response(False, "Retry could not start because the saved session does not include a record name.", diagnostic_id=diagnostic_id)
        from wingman_ai.api.record_delete import delete_record

        return delete_record(doctype=doctype, docname=docname)

    return operation_center_response(
        False,
        "Retry is not available for this operation type yet. The session is preserved for manual recovery.",
        diagnostic_id=diagnostic_id,
    )


@frappe.whitelist()
def notify_administrator(diagnostic_id=None):
    incident = get_operations_center().notify_administrator(diagnostic_id=diagnostic_id, user=current_user())
    return {
        "success": True,
        "message": f"Administrator notification prepared: {incident.get('incident_id')}.",
        "incident": incident,
        "follow_up": {
            "message": "\n".join(
                [
                    "Administrator Notification",
                    f"Incident: {incident.get('incident_id')}",
                    f"Severity: {incident.get('severity')}",
                    f"Responsible Team: {incident.get('responsible_team')}",
                    "",
                    "Current Status",
                    "- The Wingman session remains preserved.",
                    "- No Talisma OneCampus data was changed by this notification.",
                ]
            ),
            "actions": [],
        },
    }


@frappe.whitelist()
def save_draft(diagnostic_id=None, preserved_session=None, resume_later=None):
    draft = get_operations_center().save_draft(
        diagnostic_id=diagnostic_id,
        preserved_session=parse_json(preserved_session, None),
        resume_later=parse_bool(resume_later),
        user=current_user(),
    )
    return {
        "success": True,
        "message": f"Wingman saved this draft: {draft.get('draft_id')}.",
        "draft": draft,
        "follow_up": {
            "message": "\n".join(
                [
                    "Draft Saved",
                    f"Draft: {draft.get('draft_id')}",
                    "",
                    "Current Status",
                    "- Your collected values and recovery state are preserved.",
                    "- You can retry after the blocking issue is resolved.",
                ]
            ),
            "actions": [],
        },
    }


@frappe.whitelist()
def copy_diagnostic(diagnostic_id=None):
    diagnostic = get_operations_center().copy_diagnostic(diagnostic_id=diagnostic_id)
    summary = diagnostic.get("summary") or {}
    return {
        "success": True,
        "message": "Diagnostic summary prepared.",
        "diagnostic": diagnostic,
        "follow_up": {
            "message": "\n".join(
                [
                    "Diagnostic Summary",
                    f"Diagnostic: {diagnostic_id}",
                    f"Issue Type: {summary.get('issue_type')}",
                    f"Severity: {summary.get('severity')}",
                    f"Operation: {summary.get('operation')}",
                    f"Responsible Team: {summary.get('responsible_team')}",
                    "",
                    "Root Cause",
                    summary.get("root_cause") or "The issue could not be completed safely.",
                ]
            ),
            "actions": [],
        },
    }


@frappe.whitelist()
def view_technical_details(diagnostic_id=None):
    details = get_operations_center().technical_details(diagnostic_id=diagnostic_id, role_profile=current_role_profile())
    return {
        "success": True,
        "message": "Technical details prepared.",
        "technical_details": details,
        "follow_up": {
            "message": "\n".join(
                [
                    "Technical Details",
                    f"Diagnostic: {diagnostic_id}",
                    f"Component: {details.get('framework_component')}",
                    f"Failure Stage: {details.get('failure_stage')}",
                    f"Trace ID: {details.get('trace_id') or 'Not available'}",
                    "",
                    "Current Status",
                    "- Details are role-aware and sensitive values are redacted.",
                ]
            ),
            "actions": [],
        },
    }


@frappe.whitelist()
def cancel_operation(diagnostic_id=None):
    result = get_operations_center().cancel_operation(diagnostic_id=diagnostic_id, user=current_user())
    return {
        "success": True,
        "message": result.get("message"),
        "result": result,
        "follow_up": {
            "message": "\n".join(
                [
                    "Operation Cancelled",
                    "No Talisma OneCampus data was changed by Wingman.",
                ]
            ),
            "actions": [],
        },
    }


def parse_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def current_user():
    return getattr(getattr(frappe, "session", None), "user", None)


def current_role_profile():
    user = str(current_user() or "").lower()
    if user in {"administrator", "admin"}:
        return "administrator"
    if "developer" in user:
        return "developer"
    return "business_user"


def operation_center_response(success, message, diagnostic_id=None):
    return {
        "success": bool(success),
        "message": message,
        "diagnostic_id": diagnostic_id,
        "follow_up": {
            "message": message,
            "actions": [],
        },
    }
