from wingman_ai.integrations.erpnext.permissions import assert_permission


RELATED_LIMIT = 5

DISPLAY_FIELDS = {
    "Customer": ["name", "customer_name", "customer_type", "customer_group", "territory", "email_id", "mobile_no"],
    "Lead": ["name", "lead_name", "company_name", "status", "source", "email_id", "mobile_no", "territory"],
    "Sales Order": ["name", "customer", "customer_name", "status", "transaction_date", "delivery_date", "grand_total", "currency"],
    "Sales Invoice": ["name", "customer", "customer_name", "status", "posting_date", "grand_total", "outstanding_amount", "currency"],
    "Quotation": ["name", "quotation_to", "party_name", "customer_name", "status", "transaction_date", "grand_total", "currency"],
    "Opportunity": ["name", "opportunity_from", "party_name", "customer_name", "status", "sales_stage", "opportunity_amount", "expected_closing"],
    "Delivery Note": ["name", "customer", "customer_name", "status", "posting_date", "grand_total", "currency"],
    "Payment Entry": ["name", "party_type", "party", "status", "posting_date", "paid_amount", "received_amount"],
    "Communication": ["name", "subject", "communication_type", "sender", "creation"],
    "ToDo": ["name", "description", "status", "priority", "date", "allocated_to"],
    "Comment": ["name", "comment_type", "content", "owner", "creation"],
}


def get_related_summary(doctype, docname, user=None, limit=RELATED_LIMIT):
    assert_permission(doctype, "read", docname=docname, user=user)

    import frappe

    doc = frappe.get_doc(doctype, docname)
    groups = []
    skipped = []

    for spec in build_relationship_specs(doc):
        add_query_result(groups, skipped, spec, query_related(frappe, spec, limit=limit, user=user))

    activity = get_activity_summary(frappe, doctype, docname, limit=limit, user=user)
    groups.extend(activity.get("groups") or [])
    skipped.extend(activity.get("skipped") or [])

    return {
        "source_doctype": doctype,
        "source_docname": docname,
        "source_title": get_document_title(doc),
        "groups": groups,
        "skipped": skipped,
        "limit": limit,
    }


def build_relationship_specs(doc):
    doctype = doc.doctype
    docname = doc.name
    customer = first_value(doc, "customer", "party_name")
    specs = []

    if doctype == "Customer":
        specs.extend(customer_specs(docname))
    elif doctype == "Lead":
        specs.extend(
            [
                spec("Opportunities", "Opportunity", {"opportunity_from": "Lead", "party_name": docname}),
                spec("Quotations", "Quotation", {"quotation_to": "Lead", "party_name": docname}),
            ]
        )
    elif doctype == "Opportunity":
        linked_party = linked_party_spec(doc)
        if linked_party:
            specs.append(linked_party)
        specs.extend(
            [
                spec("Quotations", "Quotation", {"opportunity": docname}),
                spec("Sales Orders", "Sales Order", {"opportunity": docname}),
            ]
        )
        if customer:
            specs.extend(customer_commercial_specs(customer))
    elif doctype == "Quotation":
        specs.extend(child_parent_specs("Sales Orders", "Sales Order Item", "Sales Order", {"prevdoc_docname": docname}))
        if customer:
            specs.extend(customer_commercial_specs(customer))
    elif doctype == "Sales Order":
        specs.extend(
            child_parent_specs("Sales Invoices", "Sales Invoice Item", "Sales Invoice", {"sales_order": docname})
            + child_parent_specs("Delivery Notes", "Delivery Note Item", "Delivery Note", {"against_sales_order": docname})
            + payment_reference_specs("Payment Entries", "Sales Order", docname)
        )
        if customer:
            specs.extend([spec("Other Sales Orders for Customer", "Sales Order", {"customer": customer})])
    elif doctype == "Sales Invoice":
        specs.extend(payment_reference_specs("Payment Entries", "Sales Invoice", docname))
        if customer:
            specs.extend(customer_commercial_specs(customer))
    elif doctype == "Contact":
        linked_customers = get_linked_customer_specs_from_contact(doc)
        specs.extend(linked_customers)

    return specs


def customer_specs(customer):
    return [
        spec("Sales Orders", "Sales Order", {"customer": customer}),
        spec("Sales Invoices", "Sales Invoice", {"customer": customer}),
        spec("Quotations", "Quotation", {"quotation_to": "Customer", "party_name": customer}),
        spec("Opportunities", "Opportunity", {"opportunity_from": "Customer", "party_name": customer}),
        spec("Delivery Notes", "Delivery Note", {"customer": customer}),
        spec("Payment Entries", "Payment Entry", {"party_type": "Customer", "party": customer}),
    ]


def customer_commercial_specs(customer):
    return [
        spec("Sales Orders for Customer", "Sales Order", {"customer": customer}),
        spec("Sales Invoices for Customer", "Sales Invoice", {"customer": customer}),
        spec("Quotations for Customer", "Quotation", {"quotation_to": "Customer", "party_name": customer}),
    ]


def child_parent_specs(label, child_doctype, parent_doctype, filters):
    return [
        {
            "label": label,
            "doctype": parent_doctype,
            "child_doctype": child_doctype,
            "child_filters": filters,
            "parent_doctype": parent_doctype,
            "via_child": True,
        }
    ]


def payment_reference_specs(label, reference_doctype, reference_name):
    return child_parent_specs(
        label,
        "Payment Entry Reference",
        "Payment Entry",
        {"reference_doctype": reference_doctype, "reference_name": reference_name},
    )


def get_linked_customer_specs_from_contact(doc):
    specs = []
    for link in doc.get("links") or []:
        if link.get("link_doctype") == "Customer" and link.get("link_name"):
            specs.extend(customer_specs(link.get("link_name")))
    return specs


def spec(label, doctype, filters):
    return {"label": label, "doctype": doctype, "filters": filters}


def linked_party_spec(doc):
    party_type = doc.get("opportunity_from")
    party_name = doc.get("party_name")
    if party_type not in ("Lead", "Customer") or not party_name:
        return None
    return spec(f"Linked {party_type}", party_type, {"name": party_name})


def query_related(frappe, spec, limit=RELATED_LIMIT, user=None):
    if spec.get("via_child"):
        if not can_read_doctype(frappe, spec["parent_doctype"], user=user):
            return skipped_relation(spec, protected_doctype=spec["parent_doctype"])
        if not can_read_doctype(frappe, spec["child_doctype"], user=user):
            return skipped_relation(spec, protected_doctype=spec["child_doctype"])

        parent_names = query_child_parent_names(frappe, spec, limit=limit)
        if not parent_names:
            return []
        return query_parent_records(frappe, spec["parent_doctype"], parent_names, limit=limit, user=user)

    doctype = spec["doctype"]
    if not can_read_doctype(frappe, doctype, user=user):
        return skipped_relation(spec, protected_doctype=doctype)

    filters = valid_filters(frappe, doctype, spec.get("filters") or {})
    if not filters:
        return []

    fields = valid_fields(frappe, doctype, DISPLAY_FIELDS.get(doctype) or ["name"])
    try:
        return frappe.get_list(
            doctype,
            fields=fields,
            filters=filters,
            order_by="modified desc",
            limit_page_length=limit,
        )
    except Exception:
        return []


def query_child_parent_names(frappe, spec, limit=RELATED_LIMIT):
    child_doctype = spec["child_doctype"]
    filters = valid_filters(frappe, child_doctype, spec.get("child_filters") or {})
    if not filters:
        return []

    try:
        rows = frappe.get_list(
            child_doctype,
            fields=["parent"],
            filters=filters,
            limit_page_length=limit * 2,
        )
    except Exception:
        return []

    return unique_list(row.get("parent") for row in rows if row.get("parent"))[:limit]


def query_parent_records(frappe, doctype, parent_names, limit=RELATED_LIMIT, user=None):
    if not can_read_doctype(frappe, doctype, user=user):
        return []

    fields = valid_fields(frappe, doctype, DISPLAY_FIELDS.get(doctype) or ["name"])
    try:
        return frappe.get_list(
            doctype,
            fields=fields,
            filters={"name": ["in", parent_names]},
            order_by="modified desc",
            limit_page_length=limit,
        )
    except Exception:
        return []


def get_activity_summary(frappe, doctype, docname, limit=RELATED_LIMIT, user=None):
    activity_specs = [
        spec("Communications", "Communication", {"reference_doctype": doctype, "reference_name": docname}),
        spec("Assignments", "ToDo", {"reference_type": doctype, "reference_name": docname}),
        spec("Comments", "Comment", {"reference_doctype": doctype, "reference_name": docname}),
    ]
    groups = []
    skipped = []
    for item in activity_specs:
        add_query_result(groups, skipped, item, query_related(frappe, item, limit=limit, user=user))
    return {"groups": groups, "skipped": skipped}


def add_query_result(groups, skipped, spec, result):
    if is_skipped_relation(result):
        skipped.append(result)
        return

    if result:
        groups.append(
            {
                "label": spec["label"],
                "doctype": spec["doctype"],
                "count": len(result),
                "records": result,
            }
        )


def is_skipped_relation(result):
    return isinstance(result, dict) and result.get("skipped")


def skipped_relation(spec, protected_doctype):
    return {
        "skipped": True,
        "label": spec["label"],
        "doctype": spec.get("doctype"),
        "protected_doctype": protected_doctype,
        "reason": "read_permission_required",
    }


def can_read_doctype(frappe, doctype, user=None):
    try:
        return bool(frappe.has_permission(doctype=doctype, ptype="read", user=user))
    except TypeError:
        try:
            return bool(frappe.has_permission(doctype=doctype, ptype="read"))
        except Exception:
            return False
    except Exception:
        return False


def valid_filters(frappe, doctype, filters):
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return {}

    valid = {}
    for fieldname, value in (filters or {}).items():
        if fieldname == "name" or meta.has_field(fieldname):
            valid[fieldname] = value
    return valid


def valid_fields(frappe, doctype, fields):
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return ["name"]

    valid = []
    for fieldname in fields:
        if fieldname == "name" or meta.has_field(fieldname):
            valid.append(fieldname)
    return unique_list(valid) or ["name"]


def first_value(doc, *fieldnames):
    for fieldname in fieldnames:
        value = doc.get(fieldname)
        if value:
            return value
    return None


def get_document_title(doc):
    meta = getattr(doc, "meta", None)
    title_field = getattr(meta, "title_field", None) if meta else None
    if title_field and doc.get(title_field):
        return doc.get(title_field)
    return first_value(doc, "title", "customer_name", "lead_name", "company_name", "party_name", "name")


def unique_list(values):
    seen = set()
    unique = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
