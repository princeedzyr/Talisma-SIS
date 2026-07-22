from wingman_ai.integrations.erpnext.permissions import has_permission


def can_read(doctype, docname=None, user=None):
    return has_permission(doctype, "read", docname=docname, user=user)


def can_write(doctype, docname=None, user=None):
    return has_permission(doctype, "write", docname=docname, user=user)

