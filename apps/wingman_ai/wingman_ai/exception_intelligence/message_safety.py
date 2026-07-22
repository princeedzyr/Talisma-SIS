import json
import re


MISSING_TABLE_PATTERN = re.compile(r"Table ['\"](?P<table>[^'\"]+)['\"] doesn't exist", re.IGNORECASE)


def safe_exception_message(value):
    raw = extract_message(value)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = raw.replace("\\n", "\n")
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith(("traceback", "file ", "during handling")):
            continue
        if "/home/frappe/" in lowered or "\\apps\\" in lowered or ".py" in lowered:
            continue
        lines.append(stripped)
    cleaned = re.sub(r"\s+", " ", " ".join(lines)).strip()
    setup_message = setup_prerequisite_message(cleaned)
    return setup_message or (cleaned[:300] if cleaned else "Talisma OneCampus validation did not pass.")


def setup_prerequisite_message(message):
    match = MISSING_TABLE_PATTERN.search(message or "")
    if not match:
        return None
    table = str(match.group("table") or "").split(".")[-1]
    doctype = table[3:] if table.lower().startswith("tab") else table
    return (
        f"Talisma OneCampus setup is incomplete: the database table for {doctype} is missing. "
        "Run bench migrate for the site, clear cache, and reload Desk."
    )


def extract_message(value):
    if isinstance(value, Exception):
        value = getattr(value, "message", None) or best_exception_arg(value) or str(value)
    if isinstance(value, dict):
        return str(value.get("message") or value.get("title") or value.get("exc") or "Talisma OneCampus validation did not pass.")
    text = str(value or "")
    parsed = parse_json_message(text)
    return parsed or text


def best_exception_arg(exc):
    args = getattr(exc, "args", None) or []
    for arg in reversed(args):
        text = str(arg or "").strip()
        if text and not text.isdigit():
            return text
    for arg in args:
        text = str(arg or "").strip()
        if text:
            return text
    return None


def parse_json_message(text):
    value = str(text or "").strip()
    if not value or value[0] not in "[{":
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, list):
        return " ".join(filter(None, [parse_json_message(item) if isinstance(item, str) else extract_message(item) for item in parsed]))
    if isinstance(parsed, dict):
        return extract_message(parsed)
    return str(parsed)
