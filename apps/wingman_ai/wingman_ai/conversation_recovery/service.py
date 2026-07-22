import re

from wingman_ai.erp_service.validation import is_setup_prerequisite_message
from wingman_ai.field_filters import is_editable_business_field


RECOVERABLE_ISSUE_TYPES = {
    "mandatory",
    "field_type",
    "invalid_format",
    "invalid_value",
    "linked_document",
    "duplicate",
    "business_rule",
    "validation",
    "missing_default",
    "child_table",
}

NON_RECOVERABLE_ISSUE_TYPES = {
    "permission",
    "permission_denied",
    "authentication",
    "authorization",
    "schema",
    "database",
    "connection",
    "environment",
    "server",
    "unexpected_error",
}

NON_RECOVERABLE_MARKERS = (
    "not permitted",
    "permission",
    "login to access",
    "not allowed",
    "database table",
    "bench migrate",
    "connection refused",
    "server unavailable",
    "authentication",
)


class RecoveryDecisionEngine:
    """Classifies Talisma OneCampus responses before Wingman decides what the user sees."""

    def decide_validation(self, doctype, operation, issues=None, fields=None, response=None):
        normalized_issues = [normalize_issue(item) for item in issues or []]
        if not normalized_issues:
            return {
                "status": "passed",
                "recoverable": True,
                "kind": "passed",
                "field": None,
                "issues": [],
                "guidance": None,
                "response": response,
            }

        fields = [dict(field) for field in fields or [] if field and field.get("fieldname")]
        business_fields = [field for field in fields if is_editable_business_field(field)]

        non_recoverable = first_non_recoverable_issue(normalized_issues)
        if non_recoverable:
            return {
                "status": "blocked",
                "recoverable": False,
                "kind": "non_recoverable",
                "field": None,
                "issues": normalized_issues,
                "guidance": non_recoverable_guidance(doctype, operation, non_recoverable),
                "blocking_message": non_recoverable.get("message"),
                "response": response,
            }

        internal_field_issue = first_internal_field_issue(normalized_issues, fields)
        if internal_field_issue:
            return {
                "status": "blocked",
                "recoverable": False,
                "kind": "non_recoverable",
                "field": None,
                "issues": normalized_issues,
                "guidance": (
                    "Talisma OneCampus returned a framework-level field issue. "
                    "This is not something the user should answer conversationally."
                ),
                "blocking_message": internal_field_issue.get("message"),
                "response": response,
            }

        alternative_field = find_alternative_field_choice(doctype, normalized_issues, business_fields)
        if alternative_field:
            return {
                "status": "needs_input",
                "recoverable": True,
                "kind": "alternative_field_choice",
                "field": alternative_field,
                "issues": normalized_issues,
                "guidance": "Choose which information you want to provide, then Wingman will continue the same workflow.",
                "blocking_message": first_issue_message(normalized_issues),
                "response": response,
            }

        field = find_issue_field(normalized_issues, business_fields)
        if field:
            return {
                "status": "needs_input",
                "recoverable": True,
                "kind": "field_collection",
                "field": field,
                "issues": normalized_issues,
                "guidance": field_guidance(doctype, operation, field),
                "blocking_message": first_issue_message(normalized_issues),
                "response": response,
            }

        primary = primary_business_field(business_fields)
        if primary and all(is_recoverable_issue(issue) for issue in normalized_issues):
            return {
                "status": "needs_input",
                "recoverable": True,
                "kind": "field_collection",
                "field": primary,
                "issues": normalized_issues,
                "guidance": field_guidance(doctype, operation, primary),
                "blocking_message": first_issue_message(normalized_issues),
                "response": response,
            }

        return {
            "status": "blocked",
            "recoverable": False,
            "kind": "non_recoverable",
            "field": None,
            "issues": normalized_issues,
            "guidance": generic_blocked_guidance(doctype, operation, first_issue_message(normalized_issues)),
            "blocking_message": first_issue_message(normalized_issues),
            "response": response,
        }


def normalize_issue(issue):
    if hasattr(issue, "to_dict"):
        issue = issue.to_dict()
    elif not isinstance(issue, dict):
        issue = {"message": str(issue or ""), "issue_type": "validation"}
    payload = dict(issue or {})
    payload["issue_type"] = str(payload.get("issue_type") or payload.get("code") or "validation").strip().lower()
    payload["message"] = safe_text(payload.get("message") or payload.get("fieldname") or "Talisma OneCampus validation did not pass.")
    return payload


def first_non_recoverable_issue(issues):
    for issue in issues or []:
        if is_non_recoverable_issue(issue):
            return issue
    return None


def first_internal_field_issue(issues, fields):
    field_map = {field.get("fieldname"): field for field in fields or [] if field.get("fieldname")}
    for issue in issues or []:
        fieldname = issue.get("fieldname")
        if fieldname and fieldname in field_map and not is_editable_business_field(field_map[fieldname]):
            return issue
    return None


def is_non_recoverable_issue(issue):
    issue_type = str((issue or {}).get("issue_type") or "").lower()
    message = safe_text((issue or {}).get("message")).lower()
    if issue_type in NON_RECOVERABLE_ISSUE_TYPES:
        return True
    if is_setup_prerequisite_message(message):
        return True
    return any(marker in message for marker in NON_RECOVERABLE_MARKERS)


def is_recoverable_issue(issue):
    if is_non_recoverable_issue(issue):
        return False
    issue_type = str((issue or {}).get("issue_type") or "").lower()
    if issue_type in RECOVERABLE_ISSUE_TYPES:
        return True
    message = safe_text((issue or {}).get("message")).lower()
    return bool(
        "required" in message
        or "mandatory" in message
        or "invalid" in message
        or "not found" in message
        or "already exists" in message
    )


def find_issue_field(issues, fields):
    field_map = {field.get("fieldname"): field for field in fields or []}
    for issue in issues or []:
        fieldname = issue.get("fieldname")
        if fieldname in field_map:
            return field_map[fieldname]

    ranked = sorted(fields or [], key=lambda item: len(field_label(item)), reverse=True)
    for issue in issues or []:
        message = normalize(issue.get("message"))
        for field in ranked:
            if any(contains_phrase(message, token) for token in field_tokens(field)):
                return field
    return None


def find_alternative_field_choice(doctype, issues, fields):
    for issue in issues or []:
        phrases = extract_alternative_phrases(issue.get("message"))
        if len(phrases) < 2:
            continue

        alternatives = []
        used = set()
        for phrase in phrases:
            field = match_alternative_phrase_to_field(phrase, fields)
            if not field or field.get("fieldname") in used:
                continue
            used.add(field.get("fieldname"))
            alternatives.append(
                {
                    "label": alternative_choice_label(phrase, field),
                    "value": field.get("fieldname"),
                    "field": field,
                }
            )

        if len(alternatives) >= 2:
            return {
                "fieldname": "__wingman_recovery_choice",
                "label": f"Who is this {doctype} for?",
                "fieldtype": "Select",
                "required": True,
                "component": {"type": "select"},
                "choices": [{"label": item["label"], "value": item["value"]} for item in alternatives],
                "alternatives": alternatives,
                "wingman_recovery": "alternative_field_choice",
                "placeholder": "Choose one option",
            }
    return None


def extract_alternative_phrases(message):
    text = safe_text(message)
    if not re.search(r"\beither\b", text, re.IGNORECASE) or not re.search(r"\bor\b", text, re.IGNORECASE):
        return []
    after_either = re.split(r"\beither\b", text, maxsplit=1, flags=re.IGNORECASE)[-1]
    after_either = re.split(r"[.;]", after_either, maxsplit=1)[0]
    parts = re.split(r"\bor\b", after_either, flags=re.IGNORECASE)
    return [clean_alternative_phrase(part) for part in parts if clean_alternative_phrase(part)]


def clean_alternative_phrase(value):
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", safe_text(value).strip(" .,:;"), flags=re.IGNORECASE)
    return cleaned.strip()


def match_alternative_phrase_to_field(phrase, fields):
    scored = []
    phrase_norm = normalize(phrase)
    phrase_tokens = set(phrase_norm.split())
    for field in fields or []:
        if not is_collectable_recovery_candidate(field):
            continue
        field_norm = normalize(f"{field.get('fieldname')} {field_label(field)}")
        score = score_phrase_field_match(phrase_norm, phrase_tokens, field_norm)
        if score:
            scored.append((score, field))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def score_phrase_field_match(phrase, phrase_tokens, field_text):
    score = 0
    if any(token in field_text for token in phrase_tokens):
        score += len(set(field_text.split()) & phrase_tokens)
    if "name" in phrase_tokens and "name" in field_text:
        score += 1
    if phrase_mentions_person(phrase) and any(token in field_text for token in ("first name", "full name", "person name", "lead name")):
        score += 5
    if phrase_mentions_organization(phrase) and any(token in field_text for token in ("organization", "company", "customer", "supplier")):
        score += 5
    if any(token in field_text for token in ("email", "phone", "mobile")):
        score -= 2
    return max(score, 0)


def is_collectable_recovery_candidate(field):
    return is_editable_business_field(field) and field.get("fieldtype") in {
        "Data",
        "Small Text",
        "Text",
        "Select",
        "Link",
        "Date",
        "Datetime",
        "Int",
        "Float",
        "Currency",
        "Percent",
        "Check",
    }


def alternative_choice_label(phrase, field):
    normalized = normalize(phrase)
    if phrase_mentions_person(normalized):
        return "Individual"
    if phrase_mentions_organization(normalized):
        return "Organization"
    return field_label(field)


def phrase_mentions_person(value):
    normalized = normalize(value)
    return any(token in normalized for token in ("person", "individual", "contact"))


def phrase_mentions_organization(value):
    normalized = normalize(value)
    return any(token in normalized for token in ("organization", "organisation", "company", "business"))


def primary_business_field(fields):
    required = [field for field in fields or [] if is_required(field)]
    for field in required + list(fields or []):
        fieldtype = field.get("fieldtype")
        if fieldtype in ("Data", "Small Text", "Text", "Select", "Link", "Date", "Datetime", "Int", "Float", "Currency", "Percent"):
            return field
    return None


def field_guidance(doctype, operation, field):
    label = field_label(field)
    action = "create" if operation == "create" else "update"
    if field.get("fieldtype") == "Link":
        return f"I need {label}. Please select an existing record or create the missing linked record before I {action} this {doctype}."
    return f"I need {label} before I {action} this {doctype}."


def non_recoverable_guidance(doctype, operation, issue):
    message = safe_text((issue or {}).get("message"))
    if is_setup_prerequisite_message(message):
        return message
    if "permission" in message.lower() or str((issue or {}).get("issue_type")).lower() in {"permission", "permission_denied"}:
        return f"Talisma OneCampus permissions are preventing this {doctype} {operation}. An administrator needs to adjust access before Wingman can continue."
    return generic_blocked_guidance(doctype, operation, message)


def generic_blocked_guidance(doctype, operation, message):
    if message:
        return f"Talisma OneCampus cannot safely continue this {doctype} {operation} yet: {message}"
    return f"Talisma OneCampus cannot safely continue this {doctype} {operation} yet."


def first_issue_message(issues):
    for issue in issues or []:
        message = safe_text(issue.get("message"))
        if message:
            return message
    return "Talisma OneCampus validation did not pass."


def field_tokens(field):
    tokens = {normalize(field.get("fieldname")), normalize(field_label(field))}
    if field.get("fieldname"):
        tokens.add(normalize(str(field.get("fieldname")).replace("_", " ")))
    if field.get("options") and field.get("fieldtype") == "Link":
        tokens.add(normalize(field.get("options")))
    if field.get("target_doctype") and field.get("fieldtype") == "Dynamic Link":
        tokens.add(normalize(field.get("target_doctype")))
    return {token for token in tokens if token and token not in {"name", "type", "status"}}


def is_required(field):
    return bool((field or {}).get("reqd") or (field or {}).get("mandatory"))


def field_label(field):
    return (field or {}).get("label") or str((field or {}).get("fieldname") or "Field").replace("_", " ").title()


def contains_phrase(text, phrase):
    return bool(re.search(rf"(?<!\w){re.escape(str(phrase or '').lower())}(?!\w)", text or ""))


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", safe_text(value).lower())).strip()


def safe_text(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\\n", " ")).strip()
