import os


def get_setting(key, default=None):
    if not key:
        return default

    try:
        import frappe

        value = None
        if hasattr(frappe.conf, "get"):
            value = frappe.conf.get(key)
        if value is None:
            value = getattr(frappe.conf, key, None)
        if value is not None:
            return value
    except Exception:
        pass

    return os.environ.get(key, default)
