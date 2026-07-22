import re

from wingman_ai.application.navigation_resolver import resolve_navigation_target
from wingman_ai.integrations.erpnext.documents import get_document_summary
from wingman_ai.services.related_summary import get_related_record_response, should_summarize_related_records
from wingman_ai.services.student_summary import get_student_360_response


DETAIL_KEYWORDS = (
    "about",
    "detail",
    "details",
    "profile",
    "summary",
    "summarize",
    "explain",
    "tell me",
    "what is",
    "show me",
    "current",
    "this",
)

WRITE_KEYWORDS = ("create", "new", "add", "make", "register", "update", "change", "edit", "delete", "remove", "submit", "cancel")
READ_INTENT_CATEGORIES = {"Read", "Summarize", "Explain", "Recommend", "Search"}
EXPLICIT_RECORD_PATTERNS = (
    r"^\s*(?:please\s+)?(?:show|summarize|review|check)\s+(?:the\s+)?(?:student\s+)?(?:enrollment|courses?(?:\s+and\s+grades?)?|grades?|attendance|assessments?(?:\s+and\s+results?)?|results?|fees?|account(?:\s+balance)?|holds?|profile)\s+(?:for|of)\s+(.+?)\s*$",
    r"^\s*(?:please\s+)?what\s+is\s+(.+?)(?:'s|’s)\s+(?:account\s+)?balance\??\s*$",
    r"^\s*(?:please\s+)?(?:tell me about|summarize|give me (?:a )?summary of|summary of|details for|detail for|profile for|show details for|show me details for|show me|what is|who is|about)\s+(.+?)\s*$",
    r"^\s*(?:please\s+)?(?:fetch|read|review|look up|lookup|find)\s+(.+?)\s*$",
)
NAVIGATION_REQUEST_PATTERNS = (
    r"^\s*(?:please\s+)?(?:open|go\s+to|goto|navigate|navigae|naviagte|navgate|naviate|take\s+me\s+to|move\s+to|redirect(?:\s+to)?)\b",
)
CONTEXTUAL_REFERENCES = {
    "it",
    "this",
    "that",
    "this record",
    "that record",
    "current record",
    "the current record",
    "this page",
    "current page",
    "the current page",
    "this report",
    "current report",
    "the current report",
    "this workspace",
    "current workspace",
    "the current workspace",
}


def get_record_detail_response(doctype, docname, user=None, current=True, message=None):
    summary = get_document_summary(doctype=doctype, docname=docname, user=user)
    student_response = get_student_360_response(doctype, docname, summary, message=message)
    if student_response:
        return student_response
    return {
        "message": format_document_summary(summary, current=current),
        "data": {
            "record_summary": summary,
            "response_mode": "document_read",
            "read_only": True,
        },
    }


def get_explicit_record_response(message, context, intent=None):
    target = resolve_explicit_record_target(message, context=context)
    if not target:
        return None

    if getattr(intent, "requires_write_review", False) or is_write_request(message):
        return None

    target_data = target_to_dict(target)
    if target.kind == "document_not_found":
        return {
            "message": format_document_not_found(target.doctype, target.document_query),
            "data": {
                "record_summary": None,
                "response_mode": "explicit_document_not_found",
                "explicit_record": target_data,
                "read_only": True,
            },
        }

    if target.kind == "navigation_not_found":
        if not looks_like_record_reference(target.query or target.document_query):
            return None
        return {
            "message": format_document_not_found("record", target.document_query or target.query),
            "data": {
                "record_summary": None,
                "response_mode": "explicit_document_not_found",
                "explicit_record": target_data,
                "read_only": True,
            },
        }

    if target.kind != "document" or not target.doctype or not target.docname:
        return None

    try:
        record_context = with_target_record_context(context, target)
        if should_summarize_related_records(message, record_context, intent=intent):
            response = get_related_record_response(doctype=target.doctype, docname=target.docname, user=(context or {}).get("user"))
            response["data"]["response_mode"] = "explicit_related_record_read"
        else:
            response = get_record_detail_response(
                doctype=target.doctype,
                docname=target.docname,
                user=(context or {}).get("user"),
                current=False,
                message=message,
            )
            if not str(response["data"].get("response_mode") or "").startswith("student_"):
                response["data"]["response_mode"] = "explicit_document_read"

        response["data"]["explicit_record"] = target_data
        response["data"]["read_only"] = True
        return response
    except Exception:
        return {
            "message": format_document_read_error(target.doctype, target.docname),
            "data": {
                "record_summary": None,
                "response_mode": "explicit_document_read_error",
                "explicit_record": target_data,
                "read_only": True,
            },
        }


def resolve_explicit_record_target(message, context=None):
    record_query = extract_explicit_record_query(message)
    if not record_query:
        return None

    return resolve_navigation_target(f"open {record_query}", context=context)


def extract_explicit_record_query(message):
    text = (message or "").strip()
    if not text:
        return None
    if is_navigation_like_request(text):
        return None

    for pattern in EXPLICIT_RECORD_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            query = clean_explicit_record_query(match.group(1))
            return query if is_explicit_record_query(query) else None

    cleaned = clean_explicit_record_query(text)
    if looks_like_record_identifier(cleaned):
        return cleaned

    return None


def is_navigation_like_request(text):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in NAVIGATION_REQUEST_PATTERNS)


def clean_explicit_record_query(value):
    cleaned = re.sub(r"\s+", " ", (value or "").strip()).strip(".,;:()[]{}\"'")
    cleaned = re.sub(r"\s+\b(?:please|kindly)\b\.?$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+\b(?:in detail|for me)\b\.?$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.strip(".,;:()[]{}\"'")


def is_explicit_record_query(query):
    normalized = normalize_record_reference(query)
    if not normalized or is_contextual_reference(normalized):
        return False
    if normalized.startswith(("all ", "every ", "these ", "those ")):
        return False
    return True


def is_contextual_reference(normalized_query):
    if normalized_query in CONTEXTUAL_REFERENCES:
        return True
    return normalized_query.startswith(("this ", "that ", "current ", "the current "))


def normalize_record_reference(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", (value or "").lower())).strip()


def looks_like_record_reference(value):
    normalized = normalize_record_reference(value)
    return looks_like_record_identifier(value) or any(token.isdigit() for token in normalized.split())


def looks_like_record_identifier(value):
    text = (value or "").strip()
    if not text:
        return False
    if len(text.split()) > 6:
        return False
    return bool(re.search(r"[A-Za-z]{2,}[-/][A-Za-z0-9-]*\d", text) or re.search(r"\d{4,}", text))


def with_target_record_context(context, target):
    target_context = dict(context or {})
    target_context["object"] = {
        **((context or {}).get("object") or {}),
        "doctype": target.doctype,
        "docname": target.docname,
        "route": target.route,
    }
    return target_context


def target_to_dict(target):
    if hasattr(target, "to_dict"):
        return target.to_dict()
    return {
        "label": getattr(target, "label", ""),
        "kind": getattr(target, "kind", ""),
        "route": getattr(target, "route", []),
        "query": getattr(target, "query", ""),
        "doctype": getattr(target, "doctype", ""),
        "docname": getattr(target, "docname", ""),
        "document_query": getattr(target, "document_query", ""),
        "resolved": getattr(target, "resolved", False),
    }


def get_current_record_response(message, context, intent=None):
    context_object = (context or {}).get("object") or {}
    doctype = context_object.get("doctype")
    docname = context_object.get("docname")
    if not should_summarize_current_record(message, context, intent):
        return None

    try:
        if should_summarize_related_records(message, context, intent=intent):
            return get_related_record_response(doctype=doctype, docname=docname, user=(context or {}).get("user"))
        return get_record_detail_response(doctype=doctype, docname=docname, user=(context or {}).get("user"), message=message)
    except Exception:
        return {
            "message": format_document_read_error(doctype, docname),
            "data": {
                "record_summary": None,
                "response_mode": "document_read_error",
                "read_only": True,
            },
        }


def should_summarize_current_record(message, context, intent=None):
    context_object = (context or {}).get("object") or {}
    doctype = context_object.get("doctype")
    docname = context_object.get("docname")
    if not doctype or not docname:
        return False

    if getattr(intent, "requires_write_review", False) or is_write_request(message):
        return False

    structured = getattr(intent, "structured_intent", None) or {}
    category = structured.get("intent_category")
    if category in READ_INTENT_CATEGORIES:
        return True

    text = (message or "").lower()
    return any(keyword in text for keyword in DETAIL_KEYWORDS)


def format_document_summary(summary, current=True):
    doctype = summary.get("doctype")
    docname = summary.get("docname")
    title = summary.get("title") or docname
    status = summary.get("status")
    fields = summary.get("fields") or []
    child_tables = summary.get("child_tables") or []

    lines = [
        "Overview",
        f"I fetched the {'currently open ' if current else ''}{doctype} record: {title}.",
    ]

    if status:
        lines.append(f"Status: {status}.")

    lines.extend(["", "Filled Details"])

    if fields:
        lines.extend(format_field_lines(fields))
    else:
        lines.append("- No additional filled business fields were available on this record.")

    if child_tables:
        lines.extend(["", "Related Details"])
        for table in child_tables:
            count = table.get("count")
            label = table.get("label")
            rows_label = "row" if count == 1 else "rows"
            lines.append(f"- {label}: {count} {rows_label}")

    document_info = format_document_info(summary)
    if document_info:
        lines.extend(["", "Document Info", *document_info])

    lines.extend(
        [
            "",
            "What You Can Do Next",
            f'- Ask "open {doctype.lower()} {docname}" to return to this record from anywhere.',
            f'- Ask "open {doctype}" to go back to the {doctype} list.',
            "- Ask Wingman to summarize related orders, invoices, or activity when those connections are needed.",
        ]
    )

    return "\n".join(lines)


def format_field_lines(fields):
    lines = []
    for field in fields:
        label = field.get("label") or field.get("fieldname")
        value = field.get("value")
        if value in (None, ""):
            continue
        lines.append(f"- {label}: {value}")
    return lines


def format_document_info(summary):
    info = []
    if summary.get("owner"):
        info.append(f'- Owner: {summary["owner"]}')
    if summary.get("modified"):
        info.append(f'- Last Modified: {summary["modified"]}')
    return info


def can_summarize_record(doctype, docname):
    return bool(doctype and docname)


def is_write_request(message):
    text = (message or "").lower()
    return any(keyword in text for keyword in WRITE_KEYWORDS)


def format_document_read_error(doctype, docname):
    return "\n".join(
        [
            "Record Access",
            f"I can see that you are on {doctype} {docname}, but Talisma OneCampus did not return a readable record for it.",
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
            "- The record summary uses Talisma OneCampus read permissions.",
            "- The record may not exist, may have been renamed, or may not be readable by your role.",
            "",
            "What You Can Do Next",
            f'- Check whether {doctype} {docname} exists.',
            f'- Ask "open {doctype}" to go back to the {doctype} list.',
        ]
    )


def format_document_not_found(doctype, docname):
    label = f"{doctype} {docname}".strip() if doctype and doctype != "record" else docname
    return "\n".join(
        [
            "Record Lookup",
            f"I could not find a readable Talisma OneCampus record matching {label}.",
            "",
            "Current Status",
            "- No Talisma OneCampus data was changed.",
            "- I only used Talisma OneCampus read permissions.",
            "- The record may not exist, may be named differently, or may not be readable by your role.",
            "",
            "What You Can Do Next",
            "- Check the record ID or name and try again.",
            '- Try "open students", "open curriculum versions", or another OneCampus list.',
        ]
    )
