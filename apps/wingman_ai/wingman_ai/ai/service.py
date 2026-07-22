from wingman_ai.ai.errors import AIError
from wingman_ai.ai.providers.factory import get_ai_provider
from wingman_ai.ai.types import AIRequest
from wingman_ai.config.settings import get_wingman_settings
from wingman_ai.logging.service import log_error, log_info
from wingman_ai.prompts import PromptManager


PURPOSE_BUDGETS = {
    "general assistance": {"max_tokens": 260, "timeout_seconds": 10},
    "business reasoning": {"max_tokens": 320, "timeout_seconds": 12},
    "report planning": {"max_tokens": 360, "timeout_seconds": 14},
}


class AIService:
    def __init__(self, prompt_manager=None):
        self.prompt_manager = prompt_manager or PromptManager()

    def generate(self, message, context=None, purpose="general", template_name="core_assistant"):
        provider = get_ai_provider()
        log_info("AI provider selected", provider=getattr(provider, "name", None), purpose=purpose)
        prompt = self.prompt_manager.build(template_name, message, context=context, purpose=purpose)
        budget = get_generation_budget(purpose)
        request = AIRequest(
            system_prompt=prompt["system_prompt"],
            developer_prompt=prompt["developer_prompt"],
            user_prompt=prompt["user_prompt"],
            context=context or {},
            max_tokens=budget["max_tokens"],
            timeout_seconds=budget["timeout_seconds"],
        )

        try:
            response = provider.complete(request)
        except AIError as exc:
            log_error("AI request failed", provider=getattr(provider, "name", None), error=exc.to_dict())
            return {
                "success": False,
                "error": exc.to_dict(),
                "provider": getattr(provider, "name", None),
                "prompt_version": prompt["version"],
            }

        payload = response.to_dict()
        payload["prompt_version"] = prompt["version"]
        log_info(
            "AI request completed",
            provider=payload.get("provider"),
            model=payload.get("model"),
            latency=payload.get("latency"),
        )
        return payload

    def stream(self, message, context=None, purpose="general", template_name="core_assistant"):
        provider = get_ai_provider()
        prompt = self.prompt_manager.build(template_name, message, context=context, purpose=purpose)
        request = AIRequest(
            system_prompt=prompt["system_prompt"],
            developer_prompt=prompt["developer_prompt"],
            user_prompt=prompt["user_prompt"],
            context=context or {},
            stream=True,
        )
        return provider.stream(request)


def generate_ai_response(message, context, purpose="general"):
    return AIService().generate(message=message, context=context, purpose=purpose)


def get_generation_budget(purpose):
    settings = get_wingman_settings()
    budget = PURPOSE_BUDGETS.get(purpose) or {"max_tokens": 280, "timeout_seconds": 10}
    return {
        "max_tokens": min(int(settings.ai_max_tokens), budget["max_tokens"]) if settings.ai_max_tokens else budget["max_tokens"],
        "timeout_seconds": min(int(settings.ai_timeout), budget["timeout_seconds"]) if settings.ai_timeout else budget["timeout_seconds"],
    }


__all__ = ["AIService", "generate_ai_response", "get_generation_budget"]
