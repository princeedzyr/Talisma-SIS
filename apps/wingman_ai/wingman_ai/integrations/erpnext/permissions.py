def has_permission(doctype, permission_type="read", docname=None, user=None):
    if not doctype:
        return False

    try:
        import frappe

        if docname:
            doc = frappe.get_doc(doctype, docname)
            return bool(frappe.has_permission(doc=doc, ptype=permission_type, user=user))

        return bool(frappe.has_permission(doctype=doctype, ptype=permission_type, user=user))
    except Exception:
        return False


def assert_permission(doctype, permission_type="read", docname=None, user=None):
    if has_permission(doctype, permission_type=permission_type, docname=docname, user=user):
        return

    try:
        import frappe

        frappe.throw(f"You do not have {permission_type} permission for {doctype}.")
    except ImportError:
        raise PermissionError(f"Missing {permission_type} permission for {doctype}.")

