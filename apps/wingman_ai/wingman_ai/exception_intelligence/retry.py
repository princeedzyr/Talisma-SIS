class RetryManager:
    def __init__(self, max_attempts=2):
        self.max_attempts = max_attempts

    def build_retry_state(self, recovery, preserved_session=None):
        retry_count = int((preserved_session or {}).get("retry_count") or 0)
        return {
            "retryable": bool(recovery.get("retryable")),
            "retry_count": retry_count,
            "max_attempts": self.max_attempts,
            "can_retry_now": bool(recovery.get("retryable")) and retry_count < self.max_attempts,
            "resume_from_preserved_session": bool(preserved_session),
            "resume_operation": (preserved_session or {}).get("operation"),
            "resume_step": (preserved_session or {}).get("current_step") or (preserved_session or {}).get("failure_stage"),
            "execute_only_failed_operation": True,
        }
