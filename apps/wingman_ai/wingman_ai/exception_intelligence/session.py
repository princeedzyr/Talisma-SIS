from copy import deepcopy


class SessionPreservationService:
    def preserve(self, context=None):
        context = context or {}
        session = {
            "operation": context.get("operation"),
            "doctype": context.get("doctype"),
            "docname": context.get("docname"),
            "conversation_id": context.get("conversation_id"),
            "user": context.get("user"),
            "company": context.get("company"),
            "failure_stage": context.get("failure_stage"),
            "current_step": context.get("current_step") or context.get("failure_stage"),
            "collected_fields": scrub_sensitive(context.get("data") or context.get("payload") or {}),
            "dependencies": scrub_sensitive(context.get("dependencies") or []),
            "validation_state": scrub_sensitive(context.get("validation_state") or context.get("validation_issues") or []),
            "review": scrub_sensitive(context.get("review") or context.get("resume_action") or {}),
            "resume_action": scrub_sensitive(context.get("resume_action") or {}),
            "dependency_context": scrub_sensitive(context.get("dependency_context") or {}),
            "user_input": context.get("source_message") or context.get("message"),
            "retry_count": int(context.get("retry_count") or 0),
        }
        return {key: value for key, value in session.items() if value not in (None, "", {}, [])}


def scrub_sensitive(value):
    value = deepcopy(value)
    if isinstance(value, dict):
        return {
            key: "***" if is_sensitive_key(key) else scrub_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub_sensitive(item) for item in value]
    return value


def is_sensitive_key(key):
    return any(token in str(key or "").lower() for token in ("password", "secret", "token", "api_key", "authorization"))
