import re

from wingman_ai.field_filters import is_editable_business_field, is_system_fieldname, is_truthy
from wingman_ai.operation_engine.blueprint import split_options


DERIVATION_CONFIDENCE_THRESHOLD = 0.85

SYSTEM_FIELD_GROUP = "C_SYSTEM_GENERATED"
ALWAYS_ASK_GROUP = "A_ALWAYS_ASK"
ERP_DEFAULT_GROUP = "B_ERP_DEFAULT"
CONTEXT_DERIVED_GROUP = "D_CONTEXT_DERIVED"
OPTIONAL_GROUP = "E_OPTIONAL"

ALWAYS_ASK_EXACT_FIELDNAMES = {
    "first_name",
    "last_name",
    "full_name",
    "lead_name",
    "customer_name",
    "supplier_name",
    "employee_name",
    "contact_name",
    "company_name",
    "campaign_name",
    "source_name",
    "territory_name",
    "sales_person_name",
    "opportunity_name",
    "contract_name",
    "title",
    "subject",
    "description",
    "email",
    "email_id",
    "phone",
    "mobile",
    "mobile_no",
    "address_title",
    "address_line1",
    "address_line2",
    "city",
}

ALWAYS_ASK_LABEL_TOKENS = {
    "first name",
    "last name",
    "full name",
    "customer name",
    "company name",
    "lead name",
    "email",
    "phone",
    "mobile",
    "subject",
    "description",
    "address",
}

ERP_DEFAULT_FIELD_TOKENS = {
    "company",
    "currency",
    "language",
    "territory",
    "customer_group",
    "supplier_group",
    "warehouse",
    "price_list",
    "status",
    "stage",
    "type",
    "country",
    "parent_territory",
    "parent_customer_group",
    "parent_sales_person",
    "is_group",
}

ERP_DEFAULT_LINK_TARGETS = {
    "Company",
    "Currency",
    "Territory",
    "Customer Group",
    "Supplier Group",
    "Warehouse",
    "Price List",
    "Sales Person",
}

QUESTIONABLE_PLACEHOLDER_DEFAULTS = {"not provided", "n/a", "na", "none", "unknown", "-"}


def field_policy(field, primary_fieldname=None):
    field = dict(field or {})
    fieldname = str(field.get("fieldname") or "")
    fieldtype = field.get("fieldtype")
    label = field.get("label") or humanize(fieldname)
    editable = is_editable_business_field(field)
    system_generated = is_system_generated_field(field)
    required = is_required(field)
    default = field.get("default")
    safe_default = can_use_metadata_default(field, primary_fieldname=primary_fieldname)
    context_derivable = can_use_context_derivation(field)

    if system_generated or not editable:
        group = SYSTEM_FIELD_GROUP
        can_derive = False
        allowed_sources = []
    elif is_always_ask_field(field, primary_fieldname=primary_fieldname):
        group = ALWAYS_ASK_GROUP
        can_derive = False
        allowed_sources = ["Conversation"]
    elif context_derivable:
        group = CONTEXT_DERIVED_GROUP
        can_derive = True
        allowed_sources = ["Conversation", "Current Record", "Parent Record"]
    elif is_erp_default_field(field) or safe_default:
        group = ERP_DEFAULT_GROUP
        can_derive = True
        allowed_sources = ["Conversation", "Talisma OneCampus Default", "Metadata"]
    else:
        group = OPTIONAL_GROUP
        can_derive = False
        allowed_sources = ["Conversation"]

    expected = expected_decision(field, group=group, safe_default=safe_default)
    return {
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
        "mandatory": required,
        "conditionally_mandatory": bool(field.get("mandatory_depends_on")),
        "read_only": is_truthy(field.get("read_only")),
        "hidden": is_truthy(field.get("hidden")),
        "virtual": is_truthy(field.get("is_virtual")),
        "system_generated": system_generated,
        "editable": editable,
        "link": fieldtype in {"Link", "Dynamic Link"},
        "select": fieldtype == "Select",
        "table": fieldtype in {"Table", "Table MultiSelect"},
        "user_default": is_user_default(default),
        "company_default": is_company_default(field),
        "derived": False,
        "can_derive": can_derive,
        "derivation_policy_group": group,
        "allowed_derivation_sources": allowed_sources,
        "expected_decision": expected,
        "safe_metadata_default": safe_default,
        "safe_context_derivation": context_derivable,
        "confidence_threshold": DERIVATION_CONFIDENCE_THRESHOLD,
    }


def expected_decision(field, group=None, safe_default=False):
    if group == SYSTEM_FIELD_GROUP or not is_editable_business_field(field):
        return "Exclude"
    if safe_default and field.get("default") not in (None, ""):
        return "Use Talisma OneCampus default"
    if field.get("fieldtype") == "Check":
        return "Use Talisma OneCampus default"
    if is_required(field):
        return "Ask user"
    return "Skip unless provided"


def can_use_metadata_default(field, primary_fieldname=None):
    if not is_editable_business_field(field):
        return False
    if is_always_ask_field(field, primary_fieldname=primary_fieldname):
        return False

    fieldtype = field.get("fieldtype")
    default = field.get("default")
    normalized_default = normalize(default)
    if normalized_default in QUESTIONABLE_PLACEHOLDER_DEFAULTS:
        return False
    if fieldtype == "Check":
        return True
    if fieldtype == "Select" and default not in (None, ""):
        return default in split_options(field.get("options")) or bool(default)
    if fieldtype == "Link":
        return is_erp_default_field(field) or default not in (None, "", "__user")
    if fieldtype in {"Int", "Float", "Currency", "Percent"} and default not in (None, ""):
        return True
    if fieldtype in {"Date", "Datetime", "Time"} and default not in (None, ""):
        return True
    return default not in (None, "") and is_erp_default_field(field)


def can_use_context_derivation(field):
    if not is_editable_business_field(field):
        return False
    return field.get("fieldtype") in {"Link", "Dynamic Link"}


def is_system_generated_field(field):
    field = field or {}
    return (
        is_system_fieldname(field.get("fieldname"))
        or is_truthy(field.get("read_only"))
        or is_truthy(field.get("hidden"))
        or is_truthy(field.get("is_virtual"))
    )


def is_always_ask_field(field, primary_fieldname=None):
    field = field or {}
    fieldname = str(field.get("fieldname") or "")
    fieldtype = field.get("fieldtype")
    if not is_editable_business_field(field):
        return False
    if fieldtype in {"Select", "Check", "Link", "Dynamic Link", "Table", "Table MultiSelect"}:
        return False
    if primary_fieldname and fieldname == primary_fieldname:
        return True
    if fieldname in ALWAYS_ASK_EXACT_FIELDNAMES:
        return True
    if fieldname.endswith("_name") and not fieldname.startswith("parent_"):
        return True
    label = normalize_label(field.get("label") or "")
    if label in ALWAYS_ASK_LABEL_TOKENS:
        return True
    return any(token in label for token in ("email", "phone", "mobile", "address line"))


def is_erp_default_field(field):
    field = field or {}
    fieldname = str(field.get("fieldname") or "").lower()
    label = normalize_label(field.get("label") or "")
    options = field.get("options")
    if field.get("fieldtype") == "Link" and options in ERP_DEFAULT_LINK_TARGETS:
        return True
    normalized_name = fieldname.replace("-", "_").replace(" ", "_")
    if normalized_name in ERP_DEFAULT_FIELD_TOKENS:
        return True
    return any(token.replace("_", " ") in label for token in ERP_DEFAULT_FIELD_TOKENS)


def source_from_reason(reason):
    text = normalize(reason)
    if "current page" in text or "context" in text:
        return "Current Record"
    if "metadata" in text or "erpnext" in text:
        return "Talisma OneCampus Default"
    if "existing linked" in text:
        return "Talisma OneCampus Default"
    if "conversation" in text:
        return "Conversation"
    return "Wingman"


def confidence_for_source(source):
    return {
        "Conversation": 1.0,
        "Talisma OneCampus Default": 0.95,
        "Current Record": 0.93,
        "Parent Record": 0.9,
        "Metadata": 0.95,
        "Wingman": 0.5,
    }.get(source, 0.5)


def is_user_default(value):
    return normalize(value) in {"__user", "user", "current user"}


def is_company_default(field):
    field = field or {}
    return "company" in normalize(f"{field.get('fieldname')} {field.get('label')} {field.get('options')}")


def is_required(field):
    return is_truthy((field or {}).get("reqd")) or is_truthy((field or {}).get("mandatory"))


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").replace("_", " ").strip().lower())


def normalize_label(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def humanize(value):
    return str(value or "Field").replace("_", " ").title()
