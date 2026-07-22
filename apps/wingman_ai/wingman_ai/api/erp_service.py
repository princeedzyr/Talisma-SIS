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
from wingman_ai.erp_service import get_erp_service


@frappe.whitelist()
def create_document(doctype=None, data=None):
    payload = parse_json(data, {})
    return guarded_api_call(
        "create",
        lambda: create_document_impl(doctype, payload),
        doctype=doctype,
        data=payload,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.create_document",
    )


@frappe.whitelist()
def read_document(doctype=None, docname=None):
    return guarded_api_call(
        "read",
        lambda: read_document_impl(doctype, docname),
        doctype=doctype,
        docname=docname,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.read_document",
    )


@frappe.whitelist()
def update_document(doctype=None, docname=None, data=None):
    payload = parse_json(data, {})
    return guarded_api_call(
        "update",
        lambda: update_document_impl(doctype, docname, payload),
        doctype=doctype,
        docname=docname,
        data=payload,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.update_document",
    )


@frappe.whitelist()
def delete_document(doctype=None, docname=None):
    return guarded_api_call(
        "delete",
        lambda: delete_document_impl(doctype, docname),
        doctype=doctype,
        docname=docname,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.delete_document",
    )


@frappe.whitelist()
def list_documents(doctype=None, fields=None, filters=None, order_by=None, page=1, page_size=None):
    parsed_filters = parse_json(filters, {})
    parsed_fields = parse_sequence(fields)
    return guarded_api_call(
        "list",
        lambda: list_documents_impl(doctype, parsed_fields, parsed_filters, order_by, page, page_size),
        doctype=doctype,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.list_documents",
    )


@frappe.whitelist()
def search_documents(doctype=None, text=None, fields=None, filters=None, order_by=None, page=1, page_size=None):
    parsed_filters = parse_json(filters, {})
    parsed_fields = parse_sequence(fields)
    return guarded_api_call(
        "search",
        lambda: search_documents_impl(doctype, text, parsed_fields, parsed_filters, order_by, page, page_size),
        doctype=doctype,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.search_documents",
    )


@frappe.whitelist()
def global_search(text=None, doctypes=None, fields=None, page_size=None):
    parsed_doctypes = parse_sequence(doctypes)
    parsed_fields = parse_sequence(fields)
    return guarded_api_call(
        "global_search",
        lambda: global_search_impl(text, parsed_doctypes, parsed_fields, page_size),
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.global_search",
    )


@frappe.whitelist()
def get_metadata(doctype=None):
    return guarded_api_call(
        "metadata",
        lambda: get_metadata_impl(doctype),
        doctype=doctype,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.get_metadata",
    )


@frappe.whitelist()
def check_permissions(doctype=None, docname=None, permissions=None):
    parsed_permissions = parse_sequence(permissions)
    return guarded_api_call(
        "permissions",
        lambda: check_permissions_impl(doctype, docname, parsed_permissions),
        doctype=doctype,
        docname=docname,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.check_permissions",
    )


@frappe.whitelist()
def validate_document(doctype=None, data=None, docname=None, operation="read", run_business_hooks=False):
    payload = parse_json(data, {})
    return guarded_api_call(
        "validate",
        lambda: validate_document_impl(doctype, payload, docname, operation, run_business_hooks),
        doctype=doctype,
        docname=docname,
        data=payload,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.validate_document",
    )


@frappe.whitelist()
def get_workflow(doctype=None, docname=None):
    return guarded_api_call(
        "workflow",
        lambda: get_workflow_impl(doctype, docname),
        doctype=doctype,
        docname=docname,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.get_workflow",
    )


@frappe.whitelist()
def apply_workflow_action(doctype=None, docname=None, action=None):
    return guarded_api_call(
        "workflow_action",
        lambda: apply_workflow_action_impl(doctype, docname, action),
        doctype=doctype,
        docname=docname,
        user=current_user(),
        component="ERPServiceAPI",
        erpnext_api="wingman_ai.api.erp_service.apply_workflow_action",
    )


def create_document_impl(doctype, data):
    require_value("doctype", doctype)
    return get_erp_service().create_document(doctype=doctype, data=data, user=current_user())


def read_document_impl(doctype, docname):
    require_value("doctype", doctype)
    require_value("docname", docname)
    return get_erp_service().read_document(doctype=doctype, docname=docname, user=current_user())


def update_document_impl(doctype, docname, data):
    require_value("doctype", doctype)
    require_value("docname", docname)
    return get_erp_service().update_document(doctype=doctype, docname=docname, data=data, user=current_user())


def delete_document_impl(doctype, docname):
    require_value("doctype", doctype)
    require_value("docname", docname)
    return get_erp_service().delete_document(doctype=doctype, docname=docname, user=current_user())


def list_documents_impl(doctype, fields, filters, order_by, page, page_size):
    require_value("doctype", doctype)
    return get_erp_service().list_documents(
        doctype=doctype,
        fields=fields,
        filters=filters,
        order_by=order_by,
        page=page,
        page_size=page_size,
        user=current_user(),
    )


def search_documents_impl(doctype, text, fields, filters, order_by, page, page_size):
    require_value("doctype", doctype)
    return get_erp_service().search_documents(
        doctype=doctype,
        text=text,
        fields=fields,
        filters=filters,
        order_by=order_by,
        page=page,
        page_size=page_size,
        user=current_user(),
    )


def global_search_impl(text, doctypes, fields, page_size):
    return get_erp_service().global_search(
        text=text,
        doctypes=doctypes,
        fields=fields,
        page_size=page_size,
        user=current_user(),
    )


def get_metadata_impl(doctype):
    require_value("doctype", doctype)
    return get_erp_service().get_metadata(doctype=doctype)


def check_permissions_impl(doctype, docname, permissions):
    require_value("doctype", doctype)
    return get_erp_service().check_permissions(
        doctype=doctype,
        docname=docname,
        permissions=permissions,
        user=current_user(),
    )


def validate_document_impl(doctype, data, docname, operation, run_business_hooks):
    require_value("doctype", doctype)
    return get_erp_service().validate_document(
        doctype=doctype,
        data=data,
        docname=docname,
        operation=operation or "read",
        run_business_hooks=to_bool(run_business_hooks),
        user=current_user(),
    )


def get_workflow_impl(doctype, docname):
    require_value("doctype", doctype)
    return get_erp_service().get_workflow(doctype=doctype, docname=docname, user=current_user())


def apply_workflow_action_impl(doctype, docname, action):
    require_value("doctype", doctype)
    require_value("docname", docname)
    require_value("action", action)
    return get_erp_service().apply_workflow_action(
        doctype=doctype,
        docname=docname,
        action=action,
        user=current_user(),
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


def parse_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def parse_sequence(value):
    if value in (None, ""):
        return None
    parsed = parse_json(value, None)
    if isinstance(parsed, (list, tuple)):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, str):
        return [item.strip() for item in parsed.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else None


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes", "on")
