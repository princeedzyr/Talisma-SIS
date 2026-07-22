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

from wingman_ai.business_skills.lead_management.service import get_lead_management_service


@frappe.whitelist()
def understand_lead():
    return get_lead_management_service().understand()


@frappe.whitelist()
def create_lead(data=None):
    user = current_user()
    payload = parse_json(data, {})
    service = get_lead_management_service()
    response = service.create_lead(payload, user=user)
    if not response.get("success"):
        dependencies = service.dependency_service.detect_from_validation_response("Lead", payload, response, user=user)
        if dependencies:
            dependencies = service.record_creation_service.add_dependency_reviews(dependencies, user=user)
            parent_action = {
                "type": "create",
                "label": "Create Lead",
                "method": "wingman_ai.api.lead_management.create_lead",
                "payload": {"data": payload},
                "requires_confirmation": True,
                "auto_execute": False,
                "enabled": True,
            }
            response["follow_up"] = service.dependency_service.build_follow_up("Lead", dependencies, resume_action=parent_action)
    return response


@frappe.whitelist()
def search_leads(text=None, filters=None, page=1, page_size=10):
    return get_lead_management_service().search_leads(
        text=text,
        filters=parse_json(filters, {}),
        page=page,
        page_size=page_size,
        user=current_user(),
    )


@frappe.whitelist()
def update_lead(lead_name=None, data=None):
    require_value("lead_name", lead_name)
    return get_lead_management_service().update_lead(lead_name, parse_json(data, {}), user=current_user())


@frappe.whitelist()
def summarize_lead(lead_name=None):
    require_value("lead_name", lead_name)
    return get_lead_management_service().summarize_lead(lead_name, user=current_user())


@frappe.whitelist()
def qualify_lead(lead_name=None):
    require_value("lead_name", lead_name)
    return get_lead_management_service().qualify_lead(lead_name, user=current_user())


@frappe.whitelist()
def convert_lead(lead_name=None, execute=False):
    require_value("lead_name", lead_name)
    if to_bool(execute):
        return get_lead_management_service().convert_to_opportunity(lead_name, user=current_user())
    return get_lead_management_service().prepare_conversion(lead_name, user=current_user())


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
    return str(value).lower() in ("1", "true", "yes", "on")
