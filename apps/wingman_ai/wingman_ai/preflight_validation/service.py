import json
import re

from wingman_ai.erp_service import get_erp_service
from wingman_ai.conversation_recovery import RecoveryDecisionEngine
from wingman_ai.erp_service.validation import setup_prerequisite_message
from wingman_ai.field_filters import is_editable_business_field


class UniversalPreflightValidationEngine:
    """Runs Talisma OneCampus validation before Wingman exposes a final operation action."""

    def __init__(self, erp_service=None):
        self.erp_service = erp_service or get_erp_service()
        self.recovery = RecoveryDecisionEngine()

    def validate_create(self, doctype, data=None, fields=None, user=None):
        return self.validate(
            doctype=doctype,
            data=data or {},
            fields=fields or [],
            operation="create",
            user=user,
        )

    def validate_update(self, doctype, docname, changes=None, fields=None, user=None):
        return self.validate(
            doctype=doctype,
            docname=docname,
            data=changes or {},
            fields=fields or [],
            operation="write",
            user=user,
        )

    def validate(self, doctype, data=None, fields=None, operation="create", docname=None, user=None):
        if not hasattr(self.erp_service, "validate_document"):
            return passed_preflight()

        try:
            response = self.erp_service.validate_document(
                doctype,
                data=data or {},
                docname=docname,
                operation=operation,
                user=user,
                run_business_hooks=True,
            )
        except Exception as exc:
            issues = [{"fieldname": None, "issue_type": "business_rule", "message": safe_validation_message(exc)}]
            return self.interpret(doctype, operation, issues, fields or [], response=None)

        issues = normalize_validation_issues(response)
        if response_is_valid(response, issues):
            return passed_preflight(response=response)
        return self.interpret(doctype, operation, issues, fields or [], response=response)

    def interpret(self, doctype, operation, issues, fields, response=None):
        issues = issues or [{"fieldname": None, "issue_type": "validation", "message": "Talisma OneCampus validation did not pass."}]
        decision = self.recovery.decide_validation(doctype, operation, issues=issues, fields=fields, response=response)
        field = decision.get("field") or find_issue_field(issues, fields)
        message = first_issue_message(issues)
        guidance = decision.get("guidance") or conversational_guidance(doctype, operation, field, message)
        return {
            "valid": False,
            "recoverable": bool(decision.get("recoverable")),
            "recovery_kind": decision.get("kind"),
            "recovery_decision": decision,
            "field": field,
            "fieldname": field.get("fieldname") if field else None,
            "issues": issues,
            "guidance": guidance,
            "blocking_message": message,
            "response": response,
        }


def passed_preflight(response=None):
    return {"valid": True, "field": None, "fieldname": None, "issues": [], "guidance": None, "response": response}


def normalize_validation_issues(response):
    if not isinstance(response, dict):
        return []

    issues = []
    issues.extend(issue_to_dict(item) for item in response.get("validation_issues") or [])

    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    issues.extend(issue_to_dict(item) for item in result.get("issues") or [])

    for error in response.get("errors") or []:
        error = issue_to_dict(error)
        if error.get("message"):
            issues.append(
                {
                    "fieldname": error.get("fieldname"),
                    "issue_type": error.get("code") or error.get("issue_type") or "validation",
                    "message": safe_validation_message(error.get("message")),
                }
            )

    deduped = []
    seen = set()
    for issue in issues:
        message = safe_validation_message(issue.get("message") or issue.get("fieldname") or "Talisma OneCampus validation did not pass.")
        key = (issue.get("fieldname"), message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({**issue, "message": message})
    return deduped


def issue_to_dict(issue):
    if hasattr(issue, "to_dict"):
        return issue.to_dict()
    if isinstance(issue, dict):
        return dict(issue)
    return {"fieldname": None, "issue_type": "validation", "message": str(issue)}


def response_is_valid(response, issues):
    if not isinstance(response, dict):
        return not issues

    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    if "valid" in result:
        return bool(result.get("valid")) and not issues
    if response.get("success") is False:
        return False if issues or response.get("errors") else True
    return not issues


def find_issue_field(issues, fields):
    fields = [dict(field) for field in fields or [] if field.get("fieldname")]
    field_map = {field.get("fieldname"): field for field in fields}

    for issue in issues or []:
        fieldname = issue.get("fieldname")
        if fieldname in field_map:
            return field_map[fieldname]

    business_fields = [field for field in fields if is_user_collectable_field(field)]
    for issue in issues or []:
        message = normalize(issue.get("message"))
        if not message:
            continue
        matched = match_field_from_message(message, business_fields)
        if matched:
            return matched
    return None


def match_field_from_message(message, fields):
    ranked = sorted(fields or [], key=lambda item: len(field_label(item)), reverse=True)
    for field in ranked:
        tokens = field_tokens(field)
        if any(token and contains_phrase(message, token) for token in tokens):
            return field

    for field in ranked:
        target = normalize(field.get("options"))
        if field.get("fieldtype") == "Link" and target and contains_phrase(message, target):
            return field
        if field.get("fieldtype") == "Dynamic Link":
            dynamic_target = normalize(field.get("target_doctype"))
            if dynamic_target and contains_phrase(message, dynamic_target):
                return field
    return None


def field_tokens(field):
    tokens = {normalize(field.get("fieldname")), normalize(field_label(field))}
    if field.get("fieldname"):
        tokens.add(normalize(str(field.get("fieldname")).replace("_", " ")))
    return {token for token in tokens if token and token not in {"name", "type", "status"}}


def is_user_collectable_field(field):
    return is_editable_business_field(field)


def first_issue_message(issues):
    for issue in issues or []:
        message = safe_validation_message(issue.get("message"))
        if message:
            return message
    return "Talisma OneCampus validation did not pass."


def conversational_guidance(doctype, operation, field, message):
    action = "create" if operation == "create" else "update"
    if field:
        label = field_label(field)
        if field.get("fieldtype") == "Link":
            return f"I still need {label}. Please select or create the correct record before I {action} this {doctype}."
        return f"I still need {label} before I {action} this {doctype}."
    return f"Talisma OneCampus needs one correction before I can continue: {safe_validation_message(message)}"


def safe_validation_message(value):
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
    if setup_message:
        return setup_message
    if not cleaned:
        return "Talisma OneCampus validation did not pass."
    return cleaned[:300]


def extract_message(value):
    if isinstance(value, Exception):
        value = getattr(value, "message", None) or best_exception_arg(value) or str(value)
    if isinstance(value, dict):
        return str(value.get("message") or value.get("title") or value.get("exc") or "Talisma OneCampus validation did not pass.")
    text = str(value or "")
    parsed = parse_json_message(text)
    if parsed:
        return parsed
    return text


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
        parts = [parse_json_message(item) if isinstance(item, str) else extract_message(item) for item in parsed]
        return " ".join(part for part in parts if part)
    if isinstance(parsed, dict):
        if parsed.get("message") or parsed.get("title"):
            return str(parsed.get("message") or parsed.get("title"))
        if parsed.get("_server_messages"):
            return parse_json_message(parsed.get("_server_messages"))
    return None


def field_label(field):
    return (field or {}).get("label") or str((field or {}).get("fieldname") or "Field").replace("_", " ").title()


def contains_phrase(text, phrase):
    return re.search(rf"(?<!\w){re.escape(str(phrase or '').lower())}(?!\w)", text) is not None


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()
