from dataclasses import dataclass
import json

from wingman_ai.repositories.settings_repository import get_setting


@dataclass(frozen=True)
class WingmanSettings:
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "phi3:latest"
    ai_temperature: float = 0.2
    ai_max_tokens: int = 320
    ai_streaming_enabled: bool = False
    ai_timeout: int = 14
    ai_retry_count: int = 0
    rate_limit_per_minute: int = 120
    intent_confidence_threshold: float = 0.62
    intent_fallback_threshold: float = 0.35
    intent_supported_languages: tuple = ("en",)
    intent_version: str = "1.0.0"
    intent_feature_flags: dict = None


def get_bool_setting(key, default=False):
    value = get_setting(key, default)
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes", "on")


def get_list_setting(key, default=None):
    value = get_setting(key, default or [])
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in str(value or "").split(",") if item.strip())


def get_dict_setting(key, default=None):
    value = get_setting(key, default or {})
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return default or {}
        return parsed if isinstance(parsed, dict) else default or {}
    return default or {}


def get_wingman_settings():
    return WingmanSettings(
        ai_provider=get_setting("wingman_ai_provider", "ollama"),
        ollama_base_url=get_setting("ollama_base_url", "http://host.docker.internal:11434"),
        ollama_model=get_setting("ollama_model", "phi3:latest"),
        ai_temperature=float(get_setting("ollama_temperature", get_setting("ai_temperature", 0.2))),
        ai_max_tokens=int(get_setting("ollama_max_tokens", get_setting("ai_max_tokens", 320))),
        ai_streaming_enabled=get_bool_setting("ai_streaming_enabled", False),
        ai_timeout=int(get_setting("ollama_timeout", get_setting("ai_timeout", 14))),
        ai_retry_count=int(get_setting("ollama_retry_count", get_setting("ai_retry_count", 0))),
        rate_limit_per_minute=int(get_setting("wingman_rate_limit_per_minute", 120)),
        intent_confidence_threshold=float(get_setting("wingman_intent_confidence_threshold", 0.62)),
        intent_fallback_threshold=float(get_setting("wingman_intent_fallback_threshold", 0.35)),
        intent_supported_languages=get_list_setting("wingman_intent_supported_languages", ("en",)),
        intent_version=str(get_setting("wingman_intent_version", "1.0.0")),
        intent_feature_flags=get_dict_setting(
            "wingman_intent_feature_flags",
            {"deterministic_engine": True, "ai_assisted_intent": False},
        ),
    )
