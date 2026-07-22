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
from wingman_ai.business_skills.record_delete.formatter import format_delete_success, format_post_delete_follow_up
from wingman_ai.business_skills.record_delete.service import get_record_delete_service


@frappe.whitelist()
def delete_record(doctype=None, docname=None):
    user = current_user()

    def run():
        require_value("doctype", doctype)
        require_value("docname", docname)

        response = get_record_delete_service().delete_record(doctype=doctype, docname=docname, user=user)
        response["message"] = format_delete_success(response, doctype, docname)
        if response.get("success"):
            response["follow_up"] = format_post_delete_follow_up(doctype, docname)
        return response

    return guarded_api_call(
        "delete",
        run,
        doctype=doctype,
        docname=docname,
        user=user,
        component="RecordDeleteAPI",
        erpnext_api="wingman_ai.api.record_delete.delete_record",
    )


def current_user():
    return getattr(getattr(frappe, "session", None), "user", None)


def require_value(label, value):
    if value:
        return
    try:
        frappe.throw(f"{label} is required.")
    except AttributeError:
        raise ValueError(f"{label} is required.")
