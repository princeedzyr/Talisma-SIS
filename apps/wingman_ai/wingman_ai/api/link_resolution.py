try:
    import frappe
except ImportError:
    class _Session:
        user = None

    class _FrappeStub:
        session = _Session()

        @staticmethod
        def whitelist():
            def decorator(fn):
                return fn

            return decorator

    frappe = _FrappeStub()

from wingman_ai.link_resolution import UniversalLinkResolutionEngine


@frappe.whitelist()
def search(doctype=None, text=None, fieldname=None, page_size=8):
    if not doctype:
        return {"success": False, "message": "Linked DocType is required.", "rows": []}

    engine = UniversalLinkResolutionEngine()
    result = engine.search(
        doctype=str(doctype),
        text=text or "",
        user=current_user(),
        page_size=page_size,
    )
    return {
        "success": True,
        "doctype": result.get("doctype"),
        "fieldname": fieldname,
        "query": result.get("query"),
        "rows": result.get("rows") or [],
        "has_matches": result.get("has_matches"),
    }


def current_user():
    return getattr(getattr(frappe, "session", None), "user", None)
