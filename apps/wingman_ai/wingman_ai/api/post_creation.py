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

from wingman_ai.erp_service import get_erp_service
from wingman_ai.post_creation import PostCreationWorkflowEngine


@frappe.whitelist()
def apply_step(doctype=None, docname=None, fieldname=None, fieldtype=None, value=None, child_fieldname=None, child_doctype=None):
    require_value("doctype", doctype)
    require_value("docname", docname)
    require_value("fieldname", fieldname)

    erp_service = get_erp_service()
    engine = PostCreationWorkflowEngine(erp_service)
    data = engine.build_update_payload(fieldname, fieldtype, parse_json(value, value), child_fieldname=child_fieldname)
    response = erp_service.update_document(doctype=doctype, docname=docname, data=data, user=current_user())
    if response.get("success"):
        refreshed = erp_service.read_document(doctype=doctype, docname=docname, user=current_user())
        if refreshed.get("success"):
            response["result"] = refreshed.get("result") or response.get("result")
        response["follow_up"] = engine.next_follow_up_after_update(doctype, docname, response, completed_field=fieldname, user=current_user())
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
