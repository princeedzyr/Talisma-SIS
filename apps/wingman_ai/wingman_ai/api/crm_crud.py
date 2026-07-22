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

from wingman_ai.crm_crud import get_crm_crud_framework
from wingman_ai.crm_crud.certification import CRMCRUDCertificationRunner
from wingman_ai.crm_crud.conversation_audit import ConversationDecisionAuditor


@frappe.whitelist()
def list_crm_doctypes():
    return get_crm_crud_framework().discover_doctypes()


@frappe.whitelist()
def get_crud_blueprint(doctype=None, operation="create"):
    require_value("doctype", doctype)
    return get_crm_crud_framework().build_blueprint(doctype, operation=operation)


@frappe.whitelist()
def validate_framework(execute_writes=False, sample_data=None):
    sample_data = parse_json(sample_data, {}) if sample_data else {}

    def sample_data_factory(doctype):
        return sample_data.get(doctype) or {}

    return get_crm_crud_framework().self_validate(
        user=current_user(),
        execute_writes=to_bool(execute_writes),
        sample_data_factory=sample_data_factory if sample_data else None,
    )


@frappe.whitelist()
def certify_create_update(execute_writes=False, cleanup=False):
    if not to_bool(execute_writes):
        return {
            "success": False,
            "message": "Live certification requires execute_writes=1 so records can be created, updated, and read back.",
            "result": CRMCRUDCertificationRunner(get_crm_crud_framework()).run(
                user=current_user(),
                execute_writes=False,
                cleanup=False,
            ),
        }
    return CRMCRUDCertificationRunner(get_crm_crud_framework()).run(
        user=current_user(),
        execute_writes=True,
        cleanup=to_bool(cleanup),
    )


@frappe.whitelist()
def audit_conversation_intelligence(include_mandated=True):
    return ConversationDecisionAuditor(get_crm_crud_framework()).audit(
        user=current_user(),
        include_mandated=to_bool(include_mandated),
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


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() not in ("0", "false", "no", "off")
