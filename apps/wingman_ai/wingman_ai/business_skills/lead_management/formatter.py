from wingman_ai.business_skills.lead_management.metadata import is_business_field
from wingman_ai.review_builder.service import format_creation_review_card


def format_lead_summary(summary):
    lead = summary.get("lead") or {}
    facts = summary.get("facts") or []
    related = summary.get("related") or {}
    recommendations = summary.get("recommendations") or []
    business_state = summary.get("business_state") or {}

    title = lead.get("lead_name") or lead.get("company_name") or lead.get("name") or summary.get("lead_name")
    lines = [
        "Lead Summary",
        f"Lead: {title}",
    ]

    if business_state.get("message"):
        lines.extend(["", "Current Status", f"- {business_state['message']}"])
        for record in business_state.get("records") or []:
            lines.append(f"- {record.get('doctype')}: {format_related_business_record(record)}")

    lines.extend(
        [
            "",
            "Facts",
        ]
    )
    lines.extend(f"- {item['label']}: {item['value']}" for item in facts[:12])
    if not facts:
        lines.append("- No readable Lead fields were returned by Talisma OneCampus.")

    lines.extend(["", "Related Activity"])
    for label, records in related.items():
        lines.append(f"- {label}: {len(records or [])} found")
    if not related:
        lines.append("- No related activity was available with current permissions.")

    lines.extend(["", "AI Recommendations"])
    for item in recommendations[:4]:
        lines.append(f"- {item}")
    if not recommendations:
        lines.append("- No recommendation is available yet.")

    return "\n".join(lines)


def format_record_type_mismatch(result):
    requested_doctype = result.get("requested_doctype") or "Lead"
    requested_reference = result.get("requested_reference")
    matches = result.get("matches") or []
    primary = matches[0] if matches else {}
    actual_doctype = primary.get("doctype") or "another record type"

    lines = [
        "Record Type Check",
        f"I could not find a readable {requested_doctype} matching {requested_reference}.",
        f"I found it as {article_for(actual_doctype)} {actual_doctype} instead.",
        "",
        "Matched Record",
    ]

    if matches:
        for match in matches[:5]:
            lines.append(f"- {match.get('doctype')}: {format_related_business_record(match)}")
    else:
        lines.append("- No readable alternate record was available.")

    lines.extend(
        [
            "",
            "What You Can Do Next",
            f"- Open the {actual_doctype} record if that is what you intended.",
            f"- Ask for {requested_doctype} only when you need the source {requested_doctype} record.",
        ]
    )
    return "\n".join(lines)


def format_qualification(qualification, lead_name=None):
    lines = [
        "Lead Qualification",
        f"Lead: {lead_name or 'Current Lead'}",
        f"Score: {qualification.get('score')} / 100",
        f"Grade: {qualification.get('grade')}",
        "",
        "Reasons",
    ]
    lines.extend(f"- {item}" for item in qualification.get("reasons") or ["No qualifying facts were available."])
    lines.extend(["", "Missing Information"])
    missing = qualification.get("missing_information") or []
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- No critical missing fields detected.")
    lines.extend(["", "Recommended Next Steps"])
    lines.extend(f"- {item}" for item in qualification.get("recommended_next_steps") or [])
    return "\n".join(lines)


def format_creation_review(prepared):
    if prepared.get("review"):
        return format_creation_review_card(prepared, title="Lead Creation Review")

    lines = [
        "Lead Creation Review",
        "I prepared a Lead draft for review.",
        "",
        "Captured Details",
    ]
    for label, value in prepared.get("display_fields") or []:
        lines.append(f"- {label}: {value}")
    if not prepared.get("display_fields"):
        lines.append("- No Lead details were detected yet.")
    if prepared.get("defaults_applied"):
        lines.extend(["", "Defaults Applied"])
        for item in prepared["defaults_applied"]:
            lines.append(f"- {item.get('label')}: {item.get('value')}")
    if prepared.get("missing_fields"):
        lines.extend(["", "Missing Information"])
        lines.extend(f"- {item}" for item in prepared["missing_fields"])
    dependencies = prepared.get("missing_dependencies") or prepared.get("missing_link_dependencies") or []
    if dependencies:
        lines.extend(["", "Linked Records Needed"])
        for item in dependencies:
            lines.append(f"- {item.get('target_doctype')} {item.get('value')} is not available yet.")
    lines.extend(["", "Current Status"])
    if prepared.get("ready") and dependencies:
        lines.extend(
            [
                "- Create the linked record first, then create the Lead.",
                "- Talisma OneCampus permissions and validation rules will still be applied.",
            ]
        )
    elif prepared.get("ready"):
        lines.extend(
            [
                "- Ready to create after your confirmation.",
                "- Talisma OneCampus permissions and validation rules will still be applied.",
            ]
        )
    else:
        lines.append("- No Talisma OneCampus Lead has been created yet.")
    return "\n".join(lines)


def format_update_review(prepared):
    lines = [
        "Lead Update Review",
        f"Lead: {prepared.get('lead_name') or 'Not selected'}",
        "",
        "Proposed Changes",
    ]
    for label, value in prepared.get("display_fields") or []:
        lines.append(f"- {label}: {value}")
    if not prepared.get("display_fields"):
        lines.append("- No valid update fields were detected.")
    lines.extend(["", "Current Status", "- No Talisma OneCampus data has been changed yet."])
    return "\n".join(lines)


def format_search_results(result):
    rows = ((result or {}).get("result") or {}).get("rows") or []
    lines = ["Lead Search", f"Found {len(rows)} matching Lead record(s).", "", "Results"]
    if not rows:
        lines.append("- No Leads matched the search with your current permissions.")
    for row in rows[:10]:
        lines.append("- " + format_lead_row(row))
    return "\n".join(lines)


def format_conversion_review(prepared):
    lines = [
        "Lead Conversion Review",
        f"Lead: {prepared.get('lead_name')}",
        "",
        "Conversion Path",
        "- Lead to Opportunity",
        "",
        "Prerequisites",
    ]
    prerequisites = prepared.get("prerequisites") or []
    lines.extend(f"- {item}" for item in prerequisites) if prerequisites else lines.append("- Basic Lead details are available.")
    lines.extend(["", "Current Status", "- No Opportunity has been created yet."])
    return "\n".join(lines)


def display_fields(data, metadata):
    labels = {field.get("fieldname"): field.get("label") or titleize(field.get("fieldname")) for field in metadata.fields if is_business_field(field)}
    return [(labels.get(fieldname, titleize(fieldname)), value) for fieldname, value in (data or {}).items() if value not in (None, "")]


def fact_fields(data, metadata):
    labels = {field.get("fieldname"): field.get("label") or titleize(field.get("fieldname")) for field in metadata.fields if is_business_field(field)}
    facts = []
    for fieldname, label in labels.items():
        value = (data or {}).get(fieldname)
        if value not in (None, "", []):
            facts.append({"fieldname": fieldname, "label": label, "value": value})
    for fieldname in ("owner", "creation", "modified"):
        if (data or {}).get(fieldname):
            facts.append({"fieldname": fieldname, "label": titleize(fieldname), "value": data[fieldname]})
    return facts


def format_lead_row(row):
    parts = []
    for key in ("name", "lead_name", "company_name", "status", "source", "territory", "owner"):
        value = row.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " | ".join(parts) if parts else str(row)


def format_related_business_record(record):
    name = record.get("name")
    title = first_value(record.get("title"), record.get("lead_name"), record.get("customer_name"), record.get("company_name"), record.get("party_name"))
    status = first_value(record.get("status"), record.get("sales_stage"))
    parts = []
    if title and title != name:
        parts.append(f"{title} ({name})")
    elif name:
        parts.append(str(name))
    if status:
        parts.append(f"Status: {status}")
    return " | ".join(parts) if parts else str(record)


def article_for(value):
    return "an" if str(value or "")[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def titleize(value):
    return str(value or "").replace("_", " ").title()
