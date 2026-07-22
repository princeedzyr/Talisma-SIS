import re
from datetime import date


CREATE_WORDS = ("create", "new", "add", "register", "make")
SEARCH_WORDS = ("find", "search", "show", "list", "all")
UPDATE_WORDS = ("update", "change", "edit", "set", "assign", "mark")
SUMMARY_WORDS = ("summary", "summarize", "tell me about", "about this", "profile", "details", "who owns", "what should i do next")
QUALIFY_WORDS = ("qualify", "qualification", "score")
CONVERT_WORDS = ("convert", "opportunity")


def detect_lead_operation(message, structured_intent=None):
    text = normalize(message)
    category = (structured_intent or {}).get("intent_category")
    if any(word in text for word in CONVERT_WORDS) and "lead" in text:
        return "convert"
    if any(word in text for word in QUALIFY_WORDS) and ("lead" in text or "this" in text):
        return "qualify"
    if category == "Create" or starts_with_any(text, CREATE_WORDS):
        return "create"
    if category == "Update" or starts_with_any(text, UPDATE_WORDS):
        return "update"
    if category in ("Search", "List") or starts_with_any(text, SEARCH_WORDS):
        return "search"
    if category in ("Read", "Summarize", "Recommend") or any(word in text for word in SUMMARY_WORDS):
        return "summary"
    return "summary"


def extract_create_data(message, metadata, structured_intent=None):
    parameters = (structured_intent or {}).get("extracted_parameters") or {}
    data = {}
    set_semantic(data, metadata, "lead_name", extract_create_lead_name(message, parameters.get("name")))
    set_semantic(data, metadata, "company_name", extract_company(message))
    set_semantic(data, metadata, "email", parameters.get("email") or extract_email(message))
    set_semantic(data, metadata, "phone", parameters.get("phone") or extract_phone(message))
    set_semantic(data, metadata, "source", extract_lead_source(message, metadata))
    set_semantic(data, metadata, "territory", extract_territory(message))
    return clean_payload(data)


def extract_search_request(message, metadata):
    text = normalize(message)
    filters = {}
    query = extract_name_after(message, ("find", "search", "show", "lead", "leads"))

    if "website" in text:
        set_semantic(filters, metadata, "source", best_option(metadata, "source", "Website") or "Website")
    if "unqualified" in text:
        set_semantic(filters, metadata, "status", best_option(metadata, "status", "Unqualified") or "Unqualified")
    if "qualified" in text and "unqualified" not in text:
        set_semantic(filters, metadata, "status", best_option(metadata, "status", "Qualified") or "Qualified")
    if "today" in text:
        filters["creation"] = ["between", [str(date.today()), str(date.today())]]

    territory = extract_territory(message)
    if territory and territory.lower() not in {"website", "today"}:
        set_semantic(filters, metadata, "territory", territory)

    if query and query.lower() in {"lead", "leads", "all", "today", "website", "qualified", "unqualified"}:
        query = ""

    return {"text": clean_query(query), "filters": clean_payload(filters)}


def extract_update_request(message, metadata, context=None, structured_intent=None):
    lead_name = extract_context_lead(context) or extract_name_after(message, ("lead", "for", "update", "change", "assign"))
    data = {}
    email = extract_email(message)
    phone = extract_phone(message)
    if email:
        set_semantic(data, metadata, "email", email)
    if phone:
        set_semantic(data, metadata, "phone", phone)

    status = extract_status(message, metadata)
    if status:
        set_semantic(data, metadata, "status", status)

    source = extract_value_after(message, ("source to", "lead source to", "source"))
    if source:
        set_semantic(data, metadata, "source", source)

    territory = extract_value_after(message, ("territory to", "region to", "area to"))
    if territory:
        set_semantic(data, metadata, "territory", territory)

    owner = extract_value_after(message, ("assign to", "owner to", "sales person to"))
    if owner:
        set_semantic(data, metadata, "sales_person", owner)

    return {"lead_name": clean_query(lead_name), "data": clean_payload(data)}


def extract_target_lead(message, context=None, structured_intent=None):
    context_lead = extract_context_lead(context)
    if context_lead and re.search(r"\b(this|current)\b", message or "", re.IGNORECASE):
        return context_lead
    parameters = (structured_intent or {}).get("extracted_parameters") or {}
    return clean_query(parameters.get("name") or extract_name_after(message, ("lead", "summarize", "qualify", "convert", "about", "find")))


def extract_context_lead(context):
    context_object = (context or {}).get("object") or {}
    if context_object.get("doctype") == "Lead":
        return context_object.get("docname")
    return None


def set_semantic(data, metadata, semantic_name, value):
    fieldname = metadata.semantic_fields.get(semantic_name)
    if fieldname and value not in (None, ""):
        data[fieldname] = clean_query(value)


def best_option(metadata, semantic_name, requested):
    fieldname = metadata.semantic_fields.get(semantic_name)
    options = metadata.select_options.get(fieldname) if fieldname else []
    if not options:
        return None
    requested_norm = normalize(requested)
    for option in options:
        if normalize(option) == requested_norm:
            return option
    for option in options:
        if requested_norm and requested_norm in normalize(option):
            return option
    return None


def extract_status(message, metadata):
    text = normalize(message)
    if "mark as qualified" in text or "mark qualified" in text:
        return best_option(metadata, "status", "Qualified") or "Qualified"
    if "mark as unqualified" in text or "mark unqualified" in text:
        return best_option(metadata, "status", "Unqualified") or "Unqualified"
    value = extract_value_after(message, ("status to", "status"))
    return best_option(metadata, "status", value) or value


def extract_lead_source(message, metadata):
    text = message or ""
    explicit = extract_value_after(text, ("lead source to", "lead source", "source to", "source", "via"))
    if explicit:
        return best_option(metadata, "source", explicit) or explicit

    match = re.search(r"\bfrom\s+the\s+([A-Za-z][A-Za-z0-9 .&_-]{1,60})(?:\s+channel)?", text, re.IGNORECASE)
    if match:
        candidate = clean_query(re.sub(r"\bchannel\b", "", match.group(1), flags=re.IGNORECASE))
        if candidate and (best_option(metadata, "source", candidate) or "channel" in normalize(text)):
            return best_option(metadata, "source", candidate) or candidate
    return None


def extract_territory(message):
    text = message or ""
    lowered = normalize(text)
    if "channel" in lowered or "source" in lowered or " via " in f" {lowered} ":
        explicit = extract_value_after(text, ("territory to", "territory", "region", "area", "in"))
        return explicit
    return extract_value_after(text, ("territory to", "territory", "region", "area", "in", "from"))


def extract_company(message):
    match = re.search(r"\bfor\s+([A-Z][A-Za-z0-9 .&_-]{1,100}?)(?=\s+(?:from|in|with)\b|$)", message or "")
    return clean_query(match.group(1)) if match else None


def extract_email(message):
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", message or "", re.IGNORECASE)
    return match.group(0) if match else None


def extract_phone(message):
    match = re.search(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", message or "")
    return clean_query(match.group(0)) if match else None


def extract_create_lead_name(message, parameter_name=None):
    explicit = extract_name_after(message, ("named", "called", "name"))
    if explicit:
        return explicit

    typed = extract_name_after_create_lead(message)
    if typed:
        return typed

    if parameter_name:
        return sanitize_create_lead_name(parameter_name)

    return extract_name_after(message, ("for",))


def extract_name_after_create_lead(message):
    match = re.search(
        r"\b(?:create|new|add|register|make)\s+(?:a|an|the)?\s*leads?\s+([A-Za-z][A-Za-z0-9 .&_-]{1,100})",
        message or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    value = re.split(r"\b(?:with|for|from|in|via|source|email|phone|number|as|to|into)\b", match.group(1), flags=re.IGNORECASE)[0]
    return sanitize_create_lead_name(value)


def sanitize_create_lead_name(value):
    cleaned = re.sub(r"^\s*(?:create|new|add|register|make|draft)\s+", "", value or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = strip_lead_words(cleaned)
    return clean_query(cleaned)


def extract_name_after(message, prefixes):
    text = message or ""
    for prefix in prefixes:
        match = re.search(rf"\b{re.escape(prefix)}\s+([A-Za-z][A-Za-z0-9 .&_-]{{1,100}})", text, re.IGNORECASE)
        if match:
            value = re.split(r"\b(?:with|from|in|via|source|email|phone|number|as|to|into)\b", match.group(1), flags=re.IGNORECASE)[0]
            return clean_query(strip_lead_words(value))
    return None


def extract_value_after(message, prefixes):
    text = message or ""
    for prefix in prefixes:
        match = re.search(rf"\b{re.escape(prefix)}\s+([A-Za-z][A-Za-z0-9 .&_-]{{1,80}})", text, re.IGNORECASE)
        if match:
            value = re.split(r"\b(?:with|and|email|phone|number|status|source|territory)\b", match.group(1), flags=re.IGNORECASE)[0]
            return clean_query(strip_lead_words(value))
    return None


def strip_lead_words(value):
    return re.sub(r"(?<![A-Za-z0-9-])(leads?|profile|record)(?![A-Za-z0-9-])", " ", value or "", flags=re.IGNORECASE)


def clean_payload(data):
    return {key: value for key, value in (data or {}).items() if value not in (None, "", [])}


def clean_query(value):
    return " ".join(str(value or "").strip().strip(".,;:()[]{}\"'").split())


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


def starts_with_any(text, words):
    return any(text.startswith(word) for word in words)


def first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None
