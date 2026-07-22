from wingman_ai.link_resolution import LINK_SEARCH_METHOD
from wingman_ai.operation_engine.blueprint import split_options


LINK_COMPONENT_TYPES = {"link", "search_select"}
DYNAMIC_LINK_COMPONENT_TYPES = {"dynamic_link", "dynamic_search_select"}


def component_for_field(field):
    """Return the universal conversational UI component for an Talisma OneCampus field."""
    field = field or {}
    fieldtype = field.get("fieldtype")
    fieldname = str(field.get("fieldname") or "").lower()
    label = str(field.get("label") or "").lower()

    if fieldtype == "Link":
        return {
            "type": "link",
            "target_doctype": field.get("options"),
            "search_method": LINK_SEARCH_METHOD,
            "allow_create": True,
            "allow_create_missing": True,
        }
    if fieldtype == "Dynamic Link":
        return {
            "type": "dynamic_link",
            "dynamic_target_field": field.get("options"),
            "target_doctype": field.get("target_doctype"),
            "search_method": LINK_SEARCH_METHOD,
            "allow_create": True,
            "allow_create_missing": True,
        }
    if fieldtype == "Table":
        return {"type": "table", "child_doctype": field.get("options")}
    if fieldtype == "Table MultiSelect":
        return {"type": "multiselect", "target_doctype": field.get("options")}
    if fieldtype in {"MultiSelect", "MultiSelectPills"}:
        return {"type": "multiselect"}
    if fieldtype == "Select":
        return {"type": "select", "options": split_options(field.get("options"))}
    if fieldtype == "Check":
        return {"type": "checkbox"}
    if fieldtype == "Date":
        return {"type": "date"}
    if fieldtype == "Datetime":
        return {"type": "datetime-local"}
    if fieldtype == "Time":
        return {"type": "time"}
    if fieldtype in {"Int", "Float", "Currency", "Percent"}:
        return {"type": "number"}
    if fieldtype in {"Text", "Small Text", "Long Text", "Text Editor", "Code"}:
        return {"type": "textarea"}
    if fieldtype in {"Attach", "Attach Image"}:
        return {"type": "file"}
    if "email" in fieldname or "email" in label:
        return {"type": "email"}
    if any(token in fieldname or token in label for token in ("phone", "mobile", "contact number")):
        return {"type": "tel"}
    return {"type": "text"}


def is_link_component(component):
    return str((component or {}).get("type") or "") in LINK_COMPONENT_TYPES | DYNAMIC_LINK_COMPONENT_TYPES

