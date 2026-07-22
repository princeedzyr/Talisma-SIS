from wingman_ai.review_builder.service import format_creation_review_card


from wingman_ai.field_filters import is_editable_business_field


def format_creation_review(prepared):
    if prepared.get("review"):
        return format_creation_review_card(prepared)

    doctype = friendly_doctype(prepared.get("doctype"))
    lines = [
        "Record Creation Review",
        f"I prepared a {doctype} draft for review.",
        "",
        "Captured Details",
    ]

    display = prepared.get("display_fields") or []
    if display:
        lines.extend(f"- {label}: {format_value(value)}" for label, value in display)
    else:
        lines.append("- No details were detected yet.")

    defaults = prepared.get("defaults_applied") or []
    if defaults:
        lines.extend(["", "Defaults Applied"])
        lines.extend(f"- {item.get('label')}: {format_value(item.get('value'))}" for item in defaults)

    missing = prepared.get("missing_fields") or []
    if missing:
        next_field = prepared.get("next_missing_field") or {}
        next_label = next_field.get("label") or missing[0]
        remaining_count = max(len(missing) - 1, 0)
        lines.extend(["", "Next Required Detail", f"- {next_label}"])
        if remaining_count:
            lines.append(f"- {remaining_count} more detail(s) will follow one by one.")

    dependencies = prepared.get("missing_dependencies") or []
    if dependencies:
        lines.extend(["", "Missing Dependencies"])
        for item in dependencies:
            lines.append(f"- {item.get('target_doctype')} {item.get('value')} is required before this {doctype} can be created.")

    lines.extend(["", "Current Status"])
    if prepared.get("ready") and dependencies:
        lines.extend(
            [
                "- Create the missing linked record first.",
                f"- Wingman will continue the {doctype} creation after the dependency is created.",
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
        lines.extend(
            [
                f"- No Talisma OneCampus {doctype} has been created yet.",
                f"- Please provide {question_label(prepared)}.",
            ]
        )

    return "\n".join(lines)


def format_collection_prompt(prepared, reason=None):
    doctype = friendly_doctype(prepared.get("doctype"))
    field = prepared.get("next_missing_field") or {}
    label = field.get("label") or ((prepared.get("missing_fields") or ["Required Detail"])[0])
    lines = [
        f"Let's Complete Your {doctype}",
        "I need one more detail before I can continue.",
        "",
        "Next Required Detail",
        str(label),
    ]
    if reason:
        lines.extend(["", "Note", str(reason)])
    return "\n".join(lines)


def format_dependency_collection_prompt(prepared):
    doctype = friendly_doctype(prepared.get("doctype"))
    dependencies = prepared.get("missing_dependencies") or prepared.get("missing_link_dependencies") or []
    if not dependencies:
        return format_creation_review(prepared)

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
                f"- {target} is required before creating {doctype}.",
                f"- No Talisma OneCampus {doctype} has been created yet.",
                "",
                "What You Can Do Next",
                f"- Create {target} {value}.",
                f"- Search again and choose an existing {target}.",
                "- Cancel this workflow.",
            ]
        )
    else:
        lines.append(f"Talisma OneCampus needs these records before creating {doctype}:")
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


def format_preflight_validation_prompt(prepared):
    doctype = friendly_doctype(prepared.get("doctype"))
    preflight = prepared.get("preflight") or {}
    guidance = preflight.get("guidance") or preflight.get("blocking_message") or "Talisma OneCampus needs one correction before this can continue."
    if not preflight.get("recoverable", True):
        return "\n".join(
            [
                f"I Can't Complete This {doctype} Yet",
                str(guidance),
                "",
                "Current Status",
                "- No Talisma OneCampus data was changed.",
                "- I preserved the conversation so you can retry after this is resolved.",
            ]
        )
    return "\n".join(
        [
            f"Let's Complete Your {doctype}",
            "I need one more correction before I can continue.",
            "",
            "Next Required Detail",
            guidance,
        ]
    )


def format_draft_cancelled(doctype):
    doctype = friendly_doctype(doctype)
    return "\n".join(
        [
            "Record Creation Review",
            f"I cancelled the pending {doctype or 'record'} draft.",
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
        ]
    )


def format_field_retry(prepared, field, reason=None):
    label = field.get("label") or field.get("fieldname") or "the required detail"
    next_prompt = dict(prepared or {})
    next_prompt["next_missing_field"] = next_prompt.get("next_missing_field") or {
        "fieldname": field.get("fieldname"),
        "label": label,
        "fieldtype": field.get("fieldtype"),
        "options": field.get("options"),
    }
    return format_collection_prompt(next_prompt, reason=reason or f"I could not read a valid value for {label}.")


def question_label(prepared):
    field = prepared.get("next_missing_field") or {}
    label = field.get("label") or ((prepared.get("missing_fields") or ["the required detail"])[0])
    fieldtype = field.get("fieldtype")
    if field.get("fieldname") == "items":
        return f'{label}, for example "SKU008 qty 2"'
    if field.get("fieldname") == "requirements":
        return f'{label}, for example "Introduction to Psychology; College Writing"'
    if fieldtype == "Date":
        return f'{label}, for example "2026-07-03"'
    return label


def format_unsupported_create(message=None):
    return "\n".join(
        [
            "OneCampus Record Creation",
            "I could not identify which SIS record you want to create.",
            "",
            "What You Can Do Next",
            '- Try "create a curriculum version for Certificate in Paralegal Studies".',
            '- Try "create a course named Introduction to Psychology".',
            '- Try "create a student named Maya Patel".',
            "- Include the program or student name when the new record belongs to an existing SIS record.",
        ]
    )


def friendly_doctype(doctype):
    label = str(doctype or "record")
    return label.removeprefix("Talisma ")


def display_fields(data, fields):
    labels = {field.get("fieldname"): display_label(field, data) for field in fields if is_business_field(field)}
    rows = []
    for fieldname, value in (data or {}).items():
        if value in (None, "", []):
            continue
        rows.append((labels.get(fieldname, titleize(fieldname)), value))
    return rows


def is_business_field(field):
    return is_editable_business_field(field)


def display_label(field, data=None):
    if (field or {}).get("fieldtype") == "Dynamic Link":
        target = dynamic_link_target(field, data or {})
        if target:
            return target
    return (field or {}).get("label") or titleize((field or {}).get("fieldname"))


def dynamic_link_target(field, data):
    controller = (field or {}).get("options")
    return (data or {}).get(controller) or (field or {}).get("target_doctype") or ((field or {}).get("component") or {}).get("target_doctype")


def format_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value in (0, 1):
        return "Yes" if value else "No"
    return value


def titleize(value):
    return str(value or "").replace("_", " ").title()
