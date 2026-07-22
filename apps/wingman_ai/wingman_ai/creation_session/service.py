import re

from wingman_ai.field_behavior import component_for_field as field_behavior_component_for_field
from wingman_ai.link_resolution import UniversalLinkResolutionEngine


class CreationSessionManager:
    def __init__(self, erp_service=None):
        self.erp_service = erp_service
        self.link_resolution = UniversalLinkResolutionEngine(erp_service=erp_service)

    def serialize_field(self, field, user=None):
        field = dict(field or {})
        fieldtype = field.get("fieldtype")
        fieldname = field.get("fieldname")
        target_doctype = field.get("target_doctype") or (field.get("component") or {}).get("target_doctype")
        label = target_doctype if fieldtype == "Dynamic Link" and target_doctype else field_label(field)
        component = field.get("component") or (
            self.link_resolution.describe_field(field)
            if fieldtype == "Link"
            else field_behavior_component_for_field(field)
        )
        result = {
            "fieldname": fieldname,
            "label": label,
            "fieldtype": fieldtype,
            "options": field.get("options"),
            "component": component,
            "placeholder": field.get("placeholder") or placeholder_for_field(field, component),
            "required": field.get("required") if field.get("required") is not None else True,
        }

        choices = field.get("choices") if field.get("choices") is not None else self.choices_for_field(field, user=user)
        if choices:
            result["choices"] = choices
        recommendation = recommendation_for_field(field, choices)
        if recommendation:
            result["recommendation"] = recommendation
        for key in ("wingman_recovery", "wingman_dynamic_target_selector", "alternatives", "recovery_issue", "prompt", "original_fieldtype", "original_options"):
            if field.get(key) is not None:
                result[key] = field.get(key)
        return result

    def choices_for_field(self, field, user=None):
        fieldtype = field.get("fieldtype")
        if fieldtype == "Select":
            return [{"label": option, "value": option} for option in split_options(field.get("options"))]
        if fieldtype == "Link":
            return self.link_choices(field.get("options"), user=user)
        if fieldtype == "Dynamic Link" and (field.get("target_doctype") or (field.get("component") or {}).get("target_doctype")):
            return self.link_choices(field.get("target_doctype") or (field.get("component") or {}).get("target_doctype"), user=user)
        return []

    def link_choices(self, doctype, user=None):
        if not doctype:
            return []
        choices = []
        for row in self.link_resolution.search(doctype, text="", user=user, page_size=10).get("rows") or []:
            choice = {"label": row.get("label") or row.get("value"), "value": row.get("value") or row.get("label")}
            if row.get("description"):
                choice["description"] = row.get("description")
            if choice.get("label") and choice.get("value"):
                choices.append(choice)
        return choices


def component_for_field(field):
    return field_behavior_component_for_field(field)


def placeholder_for_field(field, component):
    label = field_label(field)
    component_type = (component or {}).get("type")
    if component_type == "email":
        return f"Enter {label}, for example john@example.com"
    if component_type == "tel":
        return f"Enter {label}"
    if component_type == "number":
        return f"Enter numeric {label}"
    if component_type == "date":
        return "YYYY-MM-DD"
    if component_type == "datetime-local":
        return "Select date and time"
    if component_type == "time":
        return "HH:MM"
    if component_type in ("link", "search_select", "dynamic_link", "dynamic_search_select"):
        return f"Search or enter {label}"
    if component_type == "table":
        return f'Enter {label}, for example "SKU008 qty 2"'
    return f"Enter {label}"


def split_options(options):
    if not options:
        return []
    if isinstance(options, (list, tuple)):
        return [str(item).strip() for item in options if str(item).strip()]
    return [line.strip() for line in str(options).replace(",", "\n").splitlines() if line.strip()]


def field_label(field):
    return (field or {}).get("label") or titleize((field or {}).get("fieldname"))


def titleize(value):
    return re.sub(r"\s+", " ", str(value or "Field").replace("_", " ")).strip().title()


def recommendation_for_field(field, choices=None):
    if not field or is_user_identity_field(field):
        return None

    fieldtype = field.get("fieldtype")
    default = field.get("default")
    choices = choices or []

    if default not in (None, "", []) and fieldtype in ("Select", "Data", "Small Text", "Text", "Int", "Float", "Currency", "Percent", "Date"):
        return {
            "value": default,
            "label": str(default),
            "reason": "Matches the Talisma OneCampus field default.",
            "confidence": 90,
        }

    if fieldtype in ("Select", "Link") and len(choices) == 1:
        choice = choices[0]
        value = choice.get("value") or choice.get("label")
        if value not in (None, "", []):
            return {
                "value": value,
                "label": choice.get("label") or str(value),
                "reason": "Only one readable option is available for this field.",
                "confidence": 85,
            }

    return None


def is_user_identity_field(field):
    text = f"{field.get('fieldname') or ''} {field.get('label') or ''}".lower()
    identity_tokens = (
        "first name",
        "last name",
        "full name",
        "email",
        "phone",
        "mobile",
        "customer name",
        "organization name",
        "lead name",
        "contact name",
    )
    exact_fieldnames = {"first_name", "last_name", "full_name", "email", "email_id", "phone", "mobile_no", "customer_name", "organization_name", "lead_name"}
    if field.get("fieldname") in exact_fieldnames:
        return True
    return any(token in text for token in identity_tokens)
