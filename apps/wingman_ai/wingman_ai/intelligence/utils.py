from datetime import datetime, timezone


def result_data(payload):
    data = (payload or {}).get("data") or {}
    return data.get("result") or data


def nested_get(source, path, default=None):
    current = source or {}
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def operation_from(payload, intent=None):
    data = (payload or {}).get("data") or {}
    result = data.get("result") or {}
    return (
        result.get("operation")
        or data.get("operation")
        or (getattr(intent, "name", None) if intent else None)
        or (payload or {}).get("capability")
        or "response"
    )


def doctype_from(payload, context=None):
    data = (payload or {}).get("data") or {}
    result = data.get("result") or {}
    summary = data.get("record_summary") or {}
    navigation = data.get("navigation") or {}
    context_object = (context or {}).get("object") or {}
    return (
        result.get("doctype")
        or summary.get("doctype")
        or navigation.get("doctype")
        or context_object.get("doctype")
        or ""
    )


def docname_from(payload, context=None):
    data = (payload or {}).get("data") or {}
    result = data.get("result") or {}
    summary = data.get("record_summary") or {}
    navigation = data.get("navigation") or {}
    context_object = (context or {}).get("object") or {}
    return (
        result.get("docname")
        or result.get("name")
        or summary.get("docname")
        or navigation.get("docname")
        or context_object.get("docname")
        or ""
    )


def validation_issues(payload):
    data = (payload or {}).get("data") or {}
    result = data.get("result") or {}
    issues = []
    issues.extend(result.get("validation_issues") or [])
    issues.extend((result.get("preflight") or {}).get("issues") or [])
    return [dict(issue) for issue in issues if isinstance(issue, dict)]


def dependencies(payload):
    data = (payload or {}).get("data") or {}
    result = data.get("result") or {}
    return list(result.get("missing_dependencies") or result.get("missing_link_dependencies") or [])


def is_ready(payload):
    data = (payload or {}).get("data") or {}
    result = data.get("result") or {}
    if "ready" in result:
        return bool(result.get("ready"))
    actions = (payload or {}).get("actions") or []
    return any(action.get("requires_confirmation") for action in actions or [])


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def clamp_score(value):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 0
    return max(0, min(100, number))


def titleize(value):
    return " ".join(part.capitalize() for part in str(value or "").replace("_", " ").split())
