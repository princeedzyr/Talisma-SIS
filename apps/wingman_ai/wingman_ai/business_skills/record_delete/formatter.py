def format_delete_review(prepared):
    doctype = prepared.get("doctype") or "Record"
    docname = prepared.get("docname") or "Not selected"
    title = prepared.get("title")
    validation_issues = prepared.get("validation_issues") or []

    lines = [
        f"{doctype} Delete Review",
        "",
        "Record",
        f"- {doctype}: {title or docname}",
    ]
    if title and title != docname:
        lines.append(f"- Record ID: {docname}")

    lines.extend(["", "Current Status"])
    if validation_issues:
        lines.append("- Talisma OneCampus did not allow this delete action yet.")
        lines.append("- No Talisma OneCampus data was changed.")
    else:
        lines.append("- Ready to delete after your confirmation.")
        lines.append("- No Talisma OneCampus data has been changed yet.")
    lines.append("- Talisma OneCampus permissions and workflow rules will be applied.")

    if validation_issues:
        lines.extend(["", "What Needs Attention"])
        for issue in validation_issues[:6]:
            lines.append(f"- {issue.get('message') or issue.get('fieldname') or 'Talisma OneCampus validation did not pass.'}")

    return "\n".join(lines)


def format_delete_selection(prepared):
    lines = [
        "Choose Record to Delete",
        f'I found more than one Talisma OneCampus record matching "{prepared.get("query") or "that request"}".',
        "",
        "Matching Records",
    ]
    options = prepared.get("options") or []
    if options:
        lines.extend(f"- {format_option_label(option)}" for option in options)
    else:
        lines.append("- No readable matching records were available.")
    lines.extend(["", "Current Status", "- I did not delete anything because the target is ambiguous."])
    return "\n".join(lines)


def format_delete_not_found(query):
    return "\n".join(
        [
            "Delete Review",
            f"I could not find a readable Talisma OneCampus record matching {query or 'that request'}.",
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
            "- Check the record ID, name, or spelling and try again.",
        ]
    )


def format_delete_success(response, doctype, docname):
    if not response.get("success"):
        return response.get("message") or "Talisma OneCampus did not complete the delete action."
    return f"{doctype} {docname} deleted successfully."


def format_post_delete_follow_up(doctype, docname):
    return {
        "message": "\n".join(
            [
                "Delete Complete",
                f"{doctype} {docname} was deleted successfully.",
                "",
                "Recommended Next Actions",
                f'- Ask "open {doctype.lower()}" to review the remaining records.',
                "- Review related reports if this record affected CRM activity.",
            ]
        ),
        "actions": [],
    }


def format_option_label(option):
    doctype = option.get("doctype")
    docname = option.get("docname")
    label = option.get("label") or ""
    prefix = f"{doctype} " if doctype else ""
    display = label[len(prefix) :] if prefix and label.startswith(prefix) else label
    if display and docname and display != docname:
        return f"{doctype}: {display} ({docname})"
    if doctype and docname:
        return f"{doctype}: {docname}"
    return label or "record"
