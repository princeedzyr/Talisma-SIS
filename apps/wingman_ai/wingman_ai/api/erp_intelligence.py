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

from wingman_ai.erp_intelligence import get_erp_intelligence_service


@frappe.whitelist()
def list_modules():
    return get_erp_intelligence_service().list_modules()


@frappe.whitelist()
def list_doctypes(module=None, include_child_tables=True):
    return get_erp_intelligence_service().list_doctypes(
        module=module,
        include_child_tables=to_bool(include_child_tables),
    )


@frappe.whitelist()
def get_doctype_metadata(doctype=None):
    require_value("doctype", doctype)
    return get_erp_intelligence_service().get_doctype_metadata(doctype)


@frappe.whitelist()
def get_relationships(doctype=None):
    return get_erp_intelligence_service().get_relationships(doctype=doctype)


@frappe.whitelist()
def get_workflow(doctype=None, docname=None):
    require_value("doctype", doctype)
    return get_erp_intelligence_service().get_workflow(doctype=doctype, docname=docname, user=current_user())


@frappe.whitelist()
def get_permissions(doctype=None, docname=None):
    require_value("doctype", doctype)
    return get_erp_intelligence_service().get_permissions(doctype=doctype, docname=docname, user=current_user())


@frappe.whitelist()
def refresh_metadata(doctype=None):
    return get_erp_intelligence_service().refresh_metadata(doctype=doctype)


@frappe.whitelist()
def search_metadata(doctype=None):
    require_value("doctype", doctype)
    return get_erp_intelligence_service().get_search_metadata(doctype=doctype)


@frappe.whitelist()
def describe_doctype(doctype=None):
    require_value("doctype", doctype)
    return get_erp_intelligence_service().describe_doctype(doctype=doctype, user=current_user())


def current_user():
    return getattr(getattr(frappe, "session", None), "user", None)


def require_value(label, value):
    if value:
        return
    try:
        frappe.throw(f"{label} is required.")
    except AttributeError:
        raise ValueError(f"{label} is required.")


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() not in ("0", "false", "no", "off")
