from datetime import datetime, timezone

from wingman_ai.review_builder.service import format_update_review_card


def format_update_collection_prompt(prepared, reason=None):
    stage = prepared.get("stage")
    next_field = prepared.get("next_missing_field") or {}
    if stage == "record_selection":
        lines = ["Select Record", "I found more than one matching record. Please choose the record to update."]
    elif stage == "field_selection":
        lines = ["Update Detail", "What would you like to update?"]
    else:
        doctype = prepared.get("doctype") or "record"
        label = next_field.get("label") or "Required Detail"
        lines = [
            f"Let's Complete This {doctype} Update",
            "I need one more detail before I can continue.",
            "",
            "Next Required Detail",
            str(label),
        ]

    if reason:
        lines.extend(["", "Note", str(reason)])
    return "\n".join(lines)


def format_update_review(prepared):
    if prepared.get("review"):
        return format_update_review_card(prepared)

    doctype = prepared.get("doctype") or "Record"
    docname = prepared.get("docname") or "Not selected"
    lines = [
        f"{doctype} Update Review",
        "",
        "Record",
        f"- {doctype}: {docname}",
        "",
        "Changes",
    ]

    changes = prepared.get("change_rows") or []
    if changes:
        for row in changes:
            lines.append(f"- {row.get('label')}: {format_value(row.get('old_value'))} -> {format_value(row.get('new_value'))}")
    else:
        lines.append("- No update values were captured yet.")

    lines.extend(["", "Business Impact"])
    impacts = prepared.get("impact") or []
    lines.extend(f"- {item}" for item in impacts) if impacts else lines.append("- No significant business impact was detected.")

    validation_issues = prepared.get("validation_issues") or []
    lines.extend(["", "Validation"])
    if validation_issues:
        for issue in validation_issues[:6]:
            lines.append(f"- {issue.get('message') or issue.get('fieldname') or 'Talisma OneCampus validation did not pass.'}")
    elif prepared.get("ready"):
        lines.append("- Ready to update after your confirmation.")
    else:
        lines.append("- More information is required before this can be updated.")

    audit = prepared.get("audit") or {}
    lines.extend(["", "Audit"])
    lines.append(f"- User: {audit.get('user') or 'Current User'}")
    lines.append(f"- Timestamp: {audit.get('timestamp') or current_timestamp()}")
    lines.append("- Talisma OneCampus permissions and validation rules will be applied.")
    return "\n".join(lines)


def format_interactive_update_review(prepared):
    doctype = prepared.get("doctype") or "Record"
    docname = prepared.get("docname") or "Not selected"
    rows = prepared.get("editable_review_fields") or []
    filled_rows = [row for row in rows if row.get("current_value") not in (None, "", [])]
    preview_rows = filled_rows[:8] or rows[:8]

    lines = [
        f"{doctype} Update Review",
        "",
        "Record",
        f"- {doctype}: {docname}",
        "",
        "Editable Information",
    ]
    if preview_rows:
        for row in preview_rows:
            lines.append(f"- {row.get('label')}: {format_value(row.get('current_value'))}")
    else:
        lines.append("- No editable business fields were found for this record.")

    if len(rows) > len(preview_rows):
        lines.append(f"- {len(rows) - len(preview_rows)} more editable fields are available below.")

    lines.extend(
        [
            "",
            "Current Status",
            "- Choose any field below to edit it.",
            "- I will prepare a final comparison before Talisma OneCampus is updated.",
        ]
    )
    return "\n".join(lines)


def format_update_blocked_prompt(prepared):
    doctype = prepared.get("doctype") or "record"
    preflight = prepared.get("preflight") or {}
    guidance = preflight.get("guidance") or preflight.get("blocking_message") or "Talisma OneCampus cannot safely continue this update yet."
    return "\n".join(
        [
            f"I Can't Complete This {doctype} Update Yet",
            str(guidance),
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
            "- I preserved the update details so you can retry after this is resolved.",
        ]
    )


def format_update_dependency_prompt(prepared):
    doctype = prepared.get("doctype") or "record"
    dependencies = prepared.get("missing_dependencies") or []
    title = "Linked Record Required" if len(dependencies) == 1 else "Linked Records Required"
    lines = [title]
    if len(dependencies) == 1:
        item = dependencies[0]
        target = item.get("target_doctype") or "record"
        value = item.get("value")
        lines.append(f"I could not find an existing {target} matching {value}.")
        matches = item.get("matches") or []
        if matches:
            lines.extend(["", "Similar Existing Records"])
            lines.extend(f"- {match.get('label') or match.get('value')}" for match in matches[:5])
        lines.extend(
            [
                "",
                "Current Status",
                f"- {target} is required before updating {doctype}.",
                "- No Talisma OneCampus data was changed.",
                "",
                "What You Can Do Next",
                f"- Create {target} {value}.",
                f"- Search again and choose an existing {target}.",
                "- Cancel this workflow.",
            ]
        )
    else:
        lines.append(f"Talisma OneCampus needs these records before updating {doctype}:")
        lines.extend(f"- {item.get('target_doctype')} {item.get('value')}" for item in dependencies)
        lines.extend(
            [
                "",
                "What You Can Do Next",
                "- Create each missing linked record.",
                "- Search again for an existing record where available.",
                "- Cancel this workflow.",
            ]
        )
    return "\n".join(lines)


def format_record_not_found(query):
    return "\n".join(
        [
            "Update Review",
            f"I could not find a readable Talisma OneCampus record matching {query or 'that request'}.",
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
            "- Please check the record name or open the record and ask again.",
        ]
    )


def format_update_cancelled(doctype=None, docname=None):
    label = " ".join(item for item in (doctype, docname) if item)
    return "\n".join(
        [
            "Update Cancelled",
            f"I cancelled the pending update{f' for {label}' if label else ''}.",
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
        ]
    )


def format_update_success(response, doctype, docname):
    if not response.get("success"):
        return response.get("message") or "Talisma OneCampus did not complete the update."
    return f"{doctype} {docname} updated successfully."


def format_post_update_follow_up(doctype, docname, undo_action=None, recommendations=None):
    lines = [
        "Update Complete",
        f"{doctype} {docname} was updated successfully.",
        "",
        "Recommended Next Actions",
    ]
    recommendations = recommendations or default_recommendations(doctype)
    lines.extend(f"- {item}" for item in recommendations)
    if undo_action:
        lines.extend(["", "Undo", "- Undo is available while Talisma OneCampus still allows these fields to be changed."])

    actions = [undo_action] if undo_action else []
    return {"message": "\n".join(lines), "actions": actions}


def default_recommendations(doctype):
    normalized = str(doctype or "").lower()
    if normalized == "user":
        return ["Review roles and permissions if access-related fields changed."]
    if normalized == "customer":
        return ["Review related contacts and addresses if customer master data changed."]
    if normalized in ("sales order", "quotation", "sales invoice"):
        return ["Review taxes, pricing, and linked transactions if commercial fields changed."]
    if normalized in ("item", "warehouse"):
        return ["Review stock and pricing reports if inventory fields changed."]
    if normalized in ("project", "task"):
        return ["Review assignments and timelines if status or ownership changed."]
    return ["Review the updated record and related reports if this change affects operations."]


def format_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value in (None, ""):
        return "Blank"
    if value in (0, 1):
        return "Yes" if value else "No"
    return value


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()
