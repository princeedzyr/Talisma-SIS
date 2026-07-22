from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter


PERMISSION_TYPES = ("read", "create", "write", "delete", "submit", "cancel", "amend")


class PermissionIntelligenceService:
    def __init__(self, adapter=None, config=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()

    def explain_permissions(self, doctype, docname=None, user=None):
        self.adapter.log("info", "ERP intelligence permission check started", doctype=doctype)
        checks = []
        for permission_type in PERMISSION_TYPES:
            allowed = self.adapter.has_permission(doctype, permission_type, docname=docname, user=user)
            checks.append(
                {
                    "permission": permission_type,
                    "allowed": allowed,
                    "explanation": self.explain(permission_type, allowed, docname_provided=bool(docname)),
                }
            )

        return {
            "doctype": doctype,
            "docname_provided": bool(docname),
            "user": user,
            "checks": checks,
            "model": "frappe_permission_model",
        }

    def explain(self, permission_type, allowed, docname_provided=False):
        scope = "this record" if docname_provided else "this DocType"
        if allowed:
            return f"Talisma OneCampus allows {permission_type} access for {scope}."
        return f"Talisma OneCampus does not allow {permission_type} access for {scope} with the current role context."
