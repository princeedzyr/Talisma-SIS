SUSPICIOUS_PROMPT_PATTERNS = (
    "ignore previous instructions",
    "bypass permissions",
    "ignore erpnext permissions",
    "reveal system prompt",
    "show hidden prompt",
)


def detect_prompt_injection(message):
    text = (message or "").lower()
    return [pattern for pattern in SUSPICIOUS_PROMPT_PATTERNS if pattern in text]


def assert_prompt_is_safe(message):
    matches = detect_prompt_injection(message)
    if matches:
        return {
            "safe": False,
            "matches": matches,
            "message": "I cannot follow instructions that attempt to bypass Talisma OneCampus security or Wingman controls.",
        }

    return {"safe": True, "matches": []}

