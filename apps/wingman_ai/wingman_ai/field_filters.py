SYSTEM_FIELD_TYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Image", "Fold", "Heading", "Read Only"}
SYSTEM_FIELDNAMES = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
    "doctype",
    "naming_series",
    "_assign",
    "_comments",
    "_liked_by",
    "_seen",
    "_user_tags",
    "__user",
    "amended_from",
    "lft",
    "rgt",
    "old_parent",
    "nsm_parent_field",
}


def is_editable_business_field(field):
    fieldname = field_value(field, "fieldname")
    fieldtype = field_value(field, "fieldtype")
    if is_system_fieldname(fieldname):
        return False
    if fieldtype in SYSTEM_FIELD_TYPES:
        return False
    if is_truthy(field_value(field, "hidden")):
        return False
    if is_truthy(field_value(field, "read_only")):
        return False
    if is_truthy(field_value(field, "is_virtual")):
        return False
    return True


def is_system_fieldname(fieldname):
    fieldname = str(fieldname or "").strip()
    return not fieldname or fieldname in SYSTEM_FIELDNAMES or fieldname.startswith("_")


def field_value(field, key, default=None):
    if isinstance(field, dict):
        return field.get(key, default)
    if hasattr(field, "get"):
        try:
            return field.get(key, default)
        except TypeError:
            pass
    return getattr(field, key, default)


def is_truthy(value):
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "none", "null")
    return bool(value)
