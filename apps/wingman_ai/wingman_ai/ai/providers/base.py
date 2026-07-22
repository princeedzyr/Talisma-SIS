from wingman_ai.ai.errors import AIError


class AIProvider:
    name = "base"

    def __init__(self, config=None):
        self.config = config

    def is_configured(self):
        return False

    def health(self):
        return {"provider": self.name, "configured": self.is_configured(), "reachable": False}

    def status(self):
        return self.health()

    def complete(self, request):
        raise NotImplementedError

    def stream(self, request):
        raise NotImplementedError


class UnsupportedProvider(AIProvider):
    def __init__(self, provider_name):
        super().__init__(config=None)
        self.name = provider_name

    def health(self):
        return {
            "provider": self.name,
            "configured": False,
            "reachable": False,
            "message": f"{self.name} provider is not implemented yet.",
        }

    def complete(self, request):
        raise AIError(
            code="provider_unavailable",
            message=f"{self.name} provider is not implemented yet.",
            provider=self.name,
            retryable=False,
        )

