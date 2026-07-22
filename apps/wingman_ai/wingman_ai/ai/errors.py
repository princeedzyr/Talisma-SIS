from dataclasses import dataclass


class AIErrorCode:
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    TIMEOUT = "timeout"
    CONTEXT_TOO_LARGE = "context_too_large"
    INVALID_PROMPT = "invalid_prompt"
    UNEXPECTED = "unexpected_exception"


@dataclass
class AIError(Exception):
    code: str
    message: str
    provider: str = None
    retryable: bool = False

    def __str__(self):
        return self.message

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "retryable": self.retryable,
        }


def provider_unavailable(message, provider=None):
    return AIError(AIErrorCode.PROVIDER_UNAVAILABLE, message, provider=provider, retryable=True)


def model_unavailable(message, provider=None):
    return AIError(AIErrorCode.MODEL_UNAVAILABLE, message, provider=provider, retryable=False)


def timeout(message, provider=None):
    return AIError(AIErrorCode.TIMEOUT, message, provider=provider, retryable=True)


def invalid_prompt(message, provider=None):
    return AIError(AIErrorCode.INVALID_PROMPT, message, provider=provider, retryable=False)


def unexpected(message, provider=None):
    return AIError(AIErrorCode.UNEXPECTED, message, provider=provider, retryable=False)

