import json
import re

from wingman_ai.erp_service.models import ValidationIssue
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.logging.service import log_warning


TYPE_CHECKS = {
    "Int": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "Float": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "Currency": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "Check": lambda value: isinstance(value, (bool, int)),
    "Data": lambda value: isinstance(value, str),
    "Small Text": lambda value: isinstance(value, str),
    "Text": lambda value: isinstance(value, str),
    "Long Text": lambda value: isinstance(value, str),
    "Date": lambda value: isinstance(value, str),
    "Datetime": lambda value: isinstance(value, str),
}

MISSING_TABLE_PATTERN = re.compile(r"Table ['\"](?P<table>[^'\"]+)['\"] doesn't exist", re.IGNORECASE)


class ERPValidationService:
    def __init__(self, repository, permission_service=None):
        self.repository = repository
        self.permission_service = permission_service

    def validate_document(self, doctype, data=None, docname=None, operation="read", user=None, run_business_hooks=False):
        data = data or {}
        issues = []
        issues.extend(self.validate_document_exists(doctype, docname) if docname and operation in ("read", "write", "delete", "submit", "cancel", "amend") else [])
        issues.extend(self.validate_permissions(doctype, docname=docname, operation=operation, user=user))
        if operation == "create":
            issues.extend(self.validate_fields(doctype, data, require_mandatory=True))
            issues.extend(self.validate_links(doctype, data))
        elif operation in ("write", "update"):
            issues.extend(self.validate_fields(doctype, data, require_mandatory=False))
            issues.extend(self.validate_links(doctype, data))

        if not issues and run_business_hooks:
            try:
                self.repository.validate_document(doctype, data, docname=docname, operation=operation)
            except Exception as exc:
                issues.append(ValidationIssue(fieldname=None, issue_type="business_rule", message=safe_validation_message(exc)))

        if issues:
            log_warning("ERP validation failed", doctype=doctype, operation=operation, issue_count=len(issues))
        return {
            "valid": not issues,
            "issues": issues,
        }

    def validate_document_exists(self, doctype, docname):
        if self.repository.exists(doctype, docname):
            return []
        return [ValidationIssue(fieldname="name", issue_type="existence", message=f"{doctype} {docname} was not found.")]

    def validate_permissions(self, doctype, docname=None, operation="read", user=None):
        if not self.permission_service:
            return []
        permission_type = permission_for_operation(operation)
        return self.permission_service.require(doctype, permission_type, docname=docname, user=user)

    def validate_fields(self, doctype, data, require_mandatory=True):
        meta = self.repository.get_meta(doctype)
        issues = []
        for field in get_fields(meta):
            if not is_editable_business_field(field):
                continue
            fieldname = get_value(field, "fieldname")
            if not fieldname:
                continue
            value = data.get(fieldname)
            if require_mandatory and is_required(field) and is_empty(value):
                issues.append(ValidationIssue(fieldname=fieldname, issue_type="mandatory", message=f"{field_label(field)} is required."))
            if not is_empty(value) and not valid_field_type(get_value(field, "fieldtype"), value):
                issues.append(ValidationIssue(fieldname=fieldname, issue_type="field_type", message=f"{field_label(field)} has an invalid value type."))
        return issues

    def validate_links(self, doctype, data):
        meta = self.repository.get_meta(doctype)
        issues = []
        for field in get_fields(meta):
            fieldtype = get_value(field, "fieldtype")
            if fieldtype not in {"Link", "Dynamic Link"} or not is_editable_business_field(field):
                continue
            fieldname = get_value(field, "fieldname")
            target_doctype = link_target_doctype(field, data)
            value = data.get(fieldname)
            if value and target_doctype and not self.repository.exists(target_doctype, value):
                issues.append(
                    ValidationIssue(
                        fieldname=fieldname,
                        issue_type="linked_document",
                        message=f"{field_label(field)} references a {target_doctype} record that was not found.",
                    )
                )
        return issues


def permission_for_operation(operation):
    return {
        "create": "create",
        "read": "read",
        "write": "write",
        "update": "write",
        "delete": "delete",
        "submit": "submit",
        "cancel": "cancel",
        "amend": "amend",
    }.get(operation, "read")


def get_fields(meta):
    if isinstance(meta, dict):
        return meta.get("fields") or []
    return getattr(meta, "fields", []) or []


def get_value(source, key, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    if hasattr(source, "get"):
        try:
            return source.get(key, default)
        except TypeError:
            pass
    return getattr(source, key, default)


def is_required(field):
    return bool(get_value(field, "reqd") or get_value(field, "mandatory"))


def is_empty(value):
    return value in (None, "", [])


def field_label(field):
    return get_value(field, "label") or get_value(field, "fieldname") or "Field"


def valid_field_type(fieldtype, value):
    checker = TYPE_CHECKS.get(fieldtype)
    return True if not checker else checker(value)


def link_target_doctype(field, data=None):
    if get_value(field, "fieldtype") == "Dynamic Link":
        controller = get_value(field, "options")
        return (data or {}).get(controller) or get_value(field, "target_doctype")
    return get_value(field, "options")


def safe_validation_message(exc):
    raw = extract_message(exc)
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


def is_setup_prerequisite_message(message):
    text = str(message or "")
    lowered = text.lower()
    return bool(setup_prerequisite_message(text) or ("erpnext setup is incomplete" in lowered and "database table" in lowered))


def extract_message(value):
    if isinstance(value, Exception):
        value = getattr(value, "message", None) or best_exception_arg(value) or str(value)
    if isinstance(value, dict):
        return str(value.get("message") or value.get("title") or "Talisma OneCampus validation did not pass.")
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
        if parsed.get("message") or parsed.get("title"):
            return str(parsed.get("message") or parsed.get("title"))
        if parsed.get("_server_messages"):
            return parse_json_message(parsed.get("_server_messages"))
    return None
