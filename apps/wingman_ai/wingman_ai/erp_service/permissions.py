from wingman_ai.erp_service.models import ValidationIssue
from wingman_ai.logging.service import log_warning


PERMISSION_TYPES = ("read", "create", "write", "delete", "submit", "cancel", "amend")


class ERPPermissionService:
    def __init__(self, repository):
        self.repository = repository

    def check(self, doctype, permission_type="read", docname=None, user=None):
        allowed = self.repository.has_permission(doctype, permission_type=permission_type, docname=docname, user=user)
        return {
            "doctype": doctype,
            "docname": docname,
            "permission": permission_type,
            "allowed": allowed,
            "explanation": explain_permission(doctype, permission_type, allowed, docname=docname),
        }

    def check_many(self, doctype, docname=None, user=None, permissions=None):
        return [
            self.check(doctype, permission_type=permission_type, docname=docname, user=user)
            for permission_type in (permissions or PERMISSION_TYPES)
        ]

    def require(self, doctype, permission_type, docname=None, user=None):
        check = self.check(doctype, permission_type=permission_type, docname=docname, user=user)
        if check["allowed"]:
            return []
        log_warning("ERP permission denied", doctype=doctype, permission=permission_type)
        return [
            ValidationIssue(
                fieldname=None,
                issue_type="permission",
                message=check["explanation"],
            )
        ]


def explain_permission(doctype, permission_type, allowed, docname=None):
    target = f"{doctype} {docname}" if docname else doctype
    if allowed:
        return f"Talisma OneCampus allows {permission_type} access for {target}."
    return f"Talisma OneCampus does not allow {permission_type} access for {target} with the current role context."
