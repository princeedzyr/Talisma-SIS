from wingman_ai.ai.providers.base import UnsupportedProvider
from wingman_ai.ai.providers.ollama import OllamaProvider
from wingman_ai.config.settings import get_wingman_settings


SUPPORTED_PROVIDER_NAMES = {"ollama", "openai", "azure_openai", "anthropic", "gemini"}


def get_ai_provider():
    settings = get_wingman_settings()
    provider_name = (settings.ai_provider or "ollama").lower()

    if provider_name == "ollama":
        return OllamaProvider(settings)

    return UnsupportedProvider(provider_name)


def get_ai_provider_status():
    provider = get_ai_provider()
    return provider.health()
