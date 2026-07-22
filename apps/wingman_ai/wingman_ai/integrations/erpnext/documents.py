from wingman_ai.integrations.erpnext.permissions import assert_permission


SKIPPED_FIELD_TYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Button",
    "Image",
    "Fold",
    "Heading",
}

CHILD_TABLE_FIELD_TYPES = {"Table", "Table MultiSelect"}

SKIPPED_FIELDNAMES = {
    "_assign",
    "_comments",
    "_liked_by",
    "_seen",
    "_user_tags",
    "amended_from",
    "idx",
    "lft",
    "nsm_parent_field",
    "old_parent",
    "parent",
    "parentfield",
    "parenttype",
    "rgt",
}

PRIORITY_FIELDS_BY_DOCTYPE = {
    "Student": [
        "talisma_student_number",
        "student_name",
        "talisma_preferred_name",
        "talisma_record_status",
        "talisma_enrollment_status",
        "talisma_primary_program",
        "talisma_academic_level",
        "talisma_class_standing",
        "talisma_advisor",
        "student_email_id",
        "student_mobile_number",
        "talisma_home_campus",
        "joining_date",
    ],
    "Customer": [
        "customer_name",
        "customer_type",
        "customer_group",
        "territory",
        "default_currency",
        "default_price_list",
        "default_bank_account",
        "tax_id",
        "customer_primary_address",
        "primary_address",
        "customer_primary_contact",
        "mobile_no",
        "email_id",
        "website",
        "market_segment",
        "industry",
    ],
    "Lead": [
        "lead_name",
        "company_name",
        "status",
        "source",
        "email_id",
        "mobile_no",
        "phone",
        "territory",
        "market_segment",
        "industry",
    ],
    "Opportunity": [
        "party_name",
        "opportunity_from",
        "status",
        "sales_stage",
        "expected_closing",
        "opportunity_amount",
        "probability",
        "customer_name",
        "contact_person",
    ],
    "Contact": [
        "first_name",
        "last_name",
        "email_id",
        "mobile_no",
        "phone",
        "company_name",
        "designation",
    ],
}


def get_document(doctype, docname, user=None):
    assert_permission(doctype, "read", docname=docname, user=user)

    import frappe

    return frappe.get_doc(doctype, docname)


def get_document_summary(doctype, docname, user=None, max_fields=18):
    assert_permission(doctype, "read", docname=docname, user=user)

    import frappe

    doc = frappe.get_doc(doctype, docname)
    meta = frappe.get_meta(doctype)
    fields = collect_filled_fields(doc, meta, max_fields=max_fields)
    child_tables = collect_child_table_counts(doc, meta)

    return {
        "doctype": doctype,
        "docname": docname,
        "title": get_document_title(doc, meta),
        "status": get_document_status(doc),
        "fields": fields,
        "child_tables": child_tables,
        "owner": normalize_value(doc.get("owner")),
        "modified": normalize_value(doc.get("modified")),
        "creation": normalize_value(doc.get("creation")),
    }


def list_documents(doctype, fields=None, filters=None, limit=20, user=None):
    assert_permission(doctype, "read", user=user)

    import frappe

    return frappe.get_list(
        doctype,
        fields=fields or ["name"],
        filters=filters or {},
        limit_page_length=limit,
    )


def collect_filled_fields(doc, meta, max_fields=18):
    collected = []
    seen = set()
    field_map = {field.fieldname: field for field in meta.fields if getattr(field, "fieldname", None)}

    for fieldname in get_ordered_fieldnames(meta.name, meta.fields):
        field = field_map.get(fieldname)
        if not field or not is_summarizable_field(field):
            continue

        value = doc.get(field.fieldname)
        if is_empty_value(value):
            continue

        collected.append(
            {
                "fieldname": field.fieldname,
                "label": field.label or field.fieldname.replace("_", " ").title(),
                "fieldtype": field.fieldtype,
                "value": normalize_value(value, field.fieldtype),
            }
        )
        seen.add(field.fieldname)

        if len(collected) >= max_fields:
            return collected

    for field in meta.fields:
        if field.fieldname in seen or not is_summarizable_field(field):
            continue

        value = doc.get(field.fieldname)
        if is_empty_value(value):
            continue

        collected.append(
            {
                "fieldname": field.fieldname,
                "label": field.label or field.fieldname.replace("_", " ").title(),
                "fieldtype": field.fieldtype,
                "value": normalize_value(value, field.fieldtype),
            }
        )

        if len(collected) >= max_fields:
            break

    return collected


def get_ordered_fieldnames(doctype, fields):
    priority = PRIORITY_FIELDS_BY_DOCTYPE.get(doctype) or []
    all_fieldnames = [field.fieldname for field in fields if getattr(field, "fieldname", None)]
    return priority + [fieldname for fieldname in all_fieldnames if fieldname not in priority]


def collect_child_table_counts(doc, meta):
    child_tables = []
    for field in meta.fields:
        if field.fieldtype not in CHILD_TABLE_FIELD_TYPES:
            continue

        rows = doc.get(field.fieldname) or []
        if not rows:
            continue

        child_tables.append(
            {
                "fieldname": field.fieldname,
                "label": field.label or field.fieldname.replace("_", " ").title(),
                "count": len(rows),
            }
        )

    return child_tables[:8]


def is_summarizable_field(field):
    if not getattr(field, "fieldname", None):
        return False
    if field.fieldname in SKIPPED_FIELDNAMES:
        return False
    if field.fieldtype in SKIPPED_FIELD_TYPES or field.fieldtype in CHILD_TABLE_FIELD_TYPES:
        return False
    if getattr(field, "hidden", 0):
        return False
    if getattr(field, "print_hide", 0) and field.fieldname not in PRIORITY_FIELDS_BY_DOCTYPE.get(getattr(field, "parent", None), []):
        return False
    return True


def is_empty_value(value):
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, tuple, dict, set)) and not value:
        return True
    return False


def normalize_value(value, fieldtype=None):
    if value is None:
        return ""
    if fieldtype == "Check":
        return "Yes" if bool(value) else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {val}" for key, val in value.items() if not is_empty_value(val))
    return str(value)


def get_document_title(doc, meta):
    title_field = getattr(meta, "title_field", None)
    if title_field and doc.get(title_field):
        return normalize_value(doc.get(title_field))
    if doc.get("customer_name"):
        return normalize_value(doc.get("customer_name"))
    if doc.get("lead_name"):
        return normalize_value(doc.get("lead_name"))
    return normalize_value(doc.get("name"))


def get_document_status(doc):
    if doc.get("disabled") is not None:
        return "Disabled" if int(doc.get("disabled") or 0) else "Enabled"

    docstatus = doc.get("docstatus")
    if docstatus is None:
        return None

    try:
        return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(int(docstatus), str(docstatus))
    except (TypeError, ValueError):
        return str(docstatus)
