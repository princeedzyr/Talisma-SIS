from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.application.navigation_resolver import resolve_navigation_target


class NavigationCapability(Capability):
    name = "navigation"

    def handle(self, message, context, intent):
        target = resolve_navigation_target(message, context=context)
        response_message = build_navigation_message(target)
        return CapabilityResult(
            message=response_message,
            actions=build_navigation_actions(target),
            data={
                "current_route": context.get("object", {}).get("route"),
                "navigation": target.to_dict(),
            },
        )


def build_navigation_message(target):
    if target.kind == "document_type_mismatch":
        actual_label = format_first_option_type(target.options)
        return "\n".join(
            [
                "Record Type Check",
                f"I could not find {target.doctype} {target.document_query}.",
                f"This looks like {actual_label} instead.",
                "",
                "Matched Record",
                *format_choice_lines(target.options),
                "",
                "Current Status",
                "- I did not navigate because the requested record type did not match.",
                "- No Talisma OneCampus data was changed.",
            ]
        )

    if target.kind == "ambiguous_document":
        return "\n".join(
            [
                "Choose Destination",
                f'I found more than one Talisma OneCampus record matching "{target.document_query or target.label}".',
                "",
                "Choose Destination",
                *format_choice_lines(target.options),
                "",
                "Current Status",
                "- I did not navigate because the destination is ambiguous.",
                "- No Talisma OneCampus data was changed.",
            ]
        )

    if target.kind == "document_not_found":
        return "\n".join(
            [
                "Navigation Result",
                f"I could not find {target.doctype} {target.document_query}.",
                "",
                "Current Status",
                "- I did not navigate because the record was not found.",
                "- No Talisma OneCampus data was changed.",
                "",
                "What You Can Do Next",
                f'- Check the record ID or spelling and try again.',
                f'- Ask "open {target.doctype}" to view the {target.doctype} list.',
            ]
        )

    if target.kind == "navigation_not_found":
        return "\n".join(
            [
                "Navigation Result",
                f"I could not find a workspace, report, page, list, or record matching {target.label}.",
                "",
                "Current Status",
                "- I did not navigate because no valid Talisma OneCampus destination was found.",
                "- No Talisma OneCampus data was changed.",
                "",
                "What You Can Do Next",
                '- Try a more specific command such as "open customer Prince".',
                '- Try a OneCampus command such as "open students", "open curriculum versions", or "open student attendance".',
            ]
        )

    return f"Navigating to {format_destination(target)}."


def build_navigation_actions(target):
    if target.kind in ("ambiguous_document", "document_type_mismatch"):
        return [
            {
                "type": "navigate",
                "label": f"Open {format_option_label(option)}",
                "target": option,
                "auto_execute": False,
                "requires_confirmation": False,
            }
            for option in target.options or []
        ]

    if not target.resolved or target.kind == "document_not_found":
        return []

    return [
        {
            "type": "navigate",
            "label": f"Navigate to {target.label}",
            "target": target.to_dict(),
            "auto_execute": True,
            "requires_confirmation": False,
        }
    ]


def format_destination(target):
    if target.kind == "document":
        return target.label or target.doctype
    if target.kind == "workspace":
        return f"the {target.label} workspace"
    if target.kind == "doctype_list":
        return f"the {target.label} list"
    if target.kind == "report":
        return f"the {target.label} report"
    if target.kind == "desk_page":
        return f"the {target.label} page"
    return target.label


def format_choice_lines(options):
    lines = []
    for option in options or []:
        lines.append(f"- {format_option_label(option)}")
    return lines or ["- No readable matching records were available."]


def format_option_label(option):
    doctype = option.get("doctype")
    docname = option.get("docname")
    label = option.get("label") or ""
    prefix = f"{doctype} " if doctype else ""
    display = label[len(prefix) :] if prefix and label.startswith(prefix) else label
    if display and docname and display != docname:
        return f"{doctype}: {display}"
    if doctype and docname:
        return f"{doctype}: {docname}"
    return label or "record"


def format_first_option_type(options):
    first = (options or [{}])[0]
    doctype = first.get("doctype") or "another record type"
    return f"{'an' if doctype[:1].lower() in {'a', 'e', 'i', 'o', 'u'} else 'a'} {doctype}"
