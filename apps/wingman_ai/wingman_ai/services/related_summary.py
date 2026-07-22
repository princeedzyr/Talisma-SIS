from wingman_ai.integrations.erpnext.relationships import get_related_summary


RELATED_KEYWORDS = (
    "related",
    "connection",
    "connections",
    "orders",
    "invoices",
    "activity",
    "activities",
    "communication",
    "communications",
    "linked",
    "history",
)


def get_related_record_response(doctype, docname, user=None):
    summary = get_related_summary(doctype=doctype, docname=docname, user=user)
    return {
        "message": format_related_summary(summary),
        "data": {
            "related_summary": summary,
            "response_mode": "related_record_read",
            "read_only": True,
        },
    }


def should_summarize_related_records(message, context, intent=None):
    context_object = (context or {}).get("object") or {}
    if not context_object.get("doctype") or not context_object.get("docname"):
        return False

    text = (message or "").lower()
    return any(keyword in text for keyword in RELATED_KEYWORDS)


def format_related_summary(summary):
    doctype = summary.get("source_doctype")
    docname = summary.get("source_docname")
    source_label = format_source_label(doctype, docname, summary.get("source_title"))
    groups = summary.get("groups") or []
    skipped = summary.get("skipped") or []

    lines = [
        "Overview",
        f"I checked related Talisma OneCampus records for {source_label}.",
        "",
        "Related Records",
    ]

    if not groups:
        lines.append("- No related orders, invoices, payments, or activity were found with your current permissions.")
    else:
        for group in groups:
            lines.extend(format_group(group))

    if skipped:
        lines.extend(["", "Skipped Connections"])
        for item in skipped:
            lines.append(f"- {format_skipped_relation(item)}")
        lines.append("- I did not bypass Talisma OneCampus permissions.")

    lines.extend(
        [
            "",
            "What You Can Do Next",
            f'- Ask "open {doctype.lower()} {docname}" to return to this record.',
            "- Ask Wingman to open any listed record by its ID.",
            "- Ask for a focused summary, such as related invoices only or recent activity only.",
        ]
    )

    return "\n".join(lines)


def format_skipped_relation(item):
    label = item.get("label") or item.get("doctype") or "Connection"
    protected_doctype = item.get("protected_doctype") or item.get("doctype") or "the related record"
    return f"{label}: your role does not have read access to {protected_doctype}."


def format_group(group):
    label = group.get("label")
    records = group.get("records") or []
    lines = [f"{label} ({len(records)})"]
    for record in records:
        lines.append(f"- {format_record(record)}")
    return lines


def format_record(record):
    name = record.get("name") or "Unnamed"
    parts = [str(name)]

    status = record.get("status")
    if status:
        parts.append(f"Status: {status}")

    date_value = first_value(record, "transaction_date", "posting_date", "delivery_date", "expected_closing", "date", "creation")
    if date_value:
        parts.append(f"Date: {date_value}")

    party = first_value(record, "customer_name", "customer", "lead_name", "company_name", "party_name", "sender", "allocated_to", "owner")
    if party:
        parts.append(f"Party: {party}")

    amount = first_value(record, "grand_total", "outstanding_amount", "opportunity_amount", "paid_amount", "received_amount")
    if amount:
        currency = record.get("currency")
        formatted = f"${amount}" if str(currency or "").upper() == "USD" else (f"{currency} {amount}" if currency else str(amount))
        parts.append(f"Amount: {formatted}")

    subject = first_value(record, "subject", "description", "content")
    if subject and len(str(subject)) <= 90:
        parts.append(str(subject))

    return " | ".join(parts)


def format_source_label(doctype, docname, title=None):
    if title and title != docname:
        return f"{doctype} {title} ({docname})"
    return f"{doctype} {docname}"


def first_value(mapping, *keys):
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None
