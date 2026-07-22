from wingman_ai.exception_intelligence.knowledge_base import classify_issue_type, lookup_known_exception
from wingman_ai.exception_intelligence.message_safety import safe_exception_message


class ExceptionClassifier:
    def classify(self, exc=None, response=None, context=None):
        context = context or {}
        text = evidence_text(exc=exc, response=response, context=context)

        for issue in validation_issues(response):
            category = classify_issue_type(issue.get("issue_type") or issue.get("code"))
            if category:
                entry = lookup_known_exception(f"{category} {text}")
                entry["category"] = category
                return entry

        return lookup_known_exception(text)


def evidence_text(exc=None, response=None, context=None):
    parts = []
    if exc:
        parts.append(type(exc).__name__)
        parts.append(safe_exception_message(exc))
    if isinstance(response, dict):
        parts.append(response.get("message") or "")
        for error in response.get("errors") or []:
            if isinstance(error, dict):
                parts.append(error.get("code") or "")
                parts.append(error.get("message") or "")
        for issue in response.get("validation_issues") or []:
            if isinstance(issue, dict):
                parts.append(issue.get("issue_type") or "")
                parts.append(issue.get("message") or "")
    if context:
        parts.extend(str(context.get(key) or "") for key in ("operation", "doctype", "failure_stage", "component"))
    return " ".join(str(part or "") for part in parts)


def validation_issues(response):
    if not isinstance(response, dict):
        return []
    return [issue for issue in response.get("validation_issues") or [] if isinstance(issue, dict)]
