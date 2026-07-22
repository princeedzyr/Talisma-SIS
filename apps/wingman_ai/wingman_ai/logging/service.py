SENSITIVE_KEYS = {"password", "api_key", "secret", "token", "authorization", "prompt", "user_prompt", "system_prompt"}


def log_info(message, **kwargs):
    write_log("info", message, **kwargs)


def log_warning(message, **kwargs):
    write_log("warning", message, **kwargs)


def log_error(message, **kwargs):
    write_log("error", message, **kwargs)


def write_log(level, message, **kwargs):
    payload = redact(kwargs)
    try:
        import frappe

        logger = frappe.logger("wingman_ai")
        getattr(logger, level, logger.info)(f"{message} | {payload}")
    except Exception:
        return


def redact(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value

