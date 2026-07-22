import json
import socket
import time
import urllib.error
import urllib.request

from wingman_ai.ai.errors import AIError, model_unavailable, provider_unavailable, timeout, unexpected
from wingman_ai.ai.providers.base import AIProvider
from wingman_ai.ai.types import AIChunk, AIResponse
from wingman_ai.logging.service import log_warning


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, config):
        super().__init__(config=config)
        self.base_url = (config.ollama_base_url or "").rstrip("/")
        self.model = config.ollama_model
        self.timeout = int(config.ai_timeout)
        self.temperature = float(config.ai_temperature)
        self.max_tokens = int(config.ai_max_tokens)
        self.retry_count = int(config.ai_retry_count)
        self.streaming_enabled = bool(config.ai_streaming_enabled)

    def is_configured(self):
        return bool(self.base_url and self.model)

    def health(self):
        payload = {
            "provider": self.name,
            "configured": self.is_configured(),
            "base_url": self.base_url,
            "model": self.model,
            "streaming_enabled": self.streaming_enabled,
        }

        if not self.is_configured():
            payload.update({"reachable": False, "model_available": False})
            return payload

        try:
            models = self.list_models(timeout_seconds=min(self.timeout, 5))
            payload["reachable"] = True
            payload["model_available"] = self.model in models
            payload["models"] = models[:20]
        except AIError as exc:
            payload["reachable"] = False
            payload["model_available"] = False
            payload["error"] = exc.to_dict()

        return payload

    def list_models(self, timeout_seconds=None):
        data = self._request("GET", "/api/tags", timeout_seconds=timeout_seconds or self.timeout)
        return [model.get("name") for model in data.get("models", []) if model.get("name")]

    def complete(self, request):
        self._validate_request(request)
        payload = self._build_payload(request, stream=False)
        start = time.time()
        response = self._request_with_retry(
            "POST",
            "/api/generate",
            payload=payload,
            timeout_seconds=request.timeout_seconds or self.timeout,
        )
        response_text = (response.get("response") or "").strip()

        if not response_text:
            raise unexpected("Ollama returned an empty response.", provider=self.name)

        return AIResponse(
            success=True,
            response_text=response_text,
            provider=self.name,
            model=self.model,
            latency=round(time.time() - start, 3),
            raw_response=response,
        )

    def stream(self, request):
        self._validate_request(request)
        payload = self._build_payload(request, stream=True)
        index = 0
        for data in self._stream_request("/api/generate", payload=payload):
            text = data.get("response") or ""
            done = bool(data.get("done"))
            yield AIChunk(text=text, index=index, done=done, metadata={"model": self.model}).to_dict()
            index += 1

    def _validate_request(self, request):
        if not self.is_configured():
            raise provider_unavailable("Ollama provider is not configured.", provider=self.name)

        if not request.user_prompt:
            raise AIError("invalid_prompt", "User prompt is required.", provider=self.name, retryable=False)

    def _build_payload(self, request, stream=False):
        prompt = request.user_prompt
        if request.developer_prompt:
            prompt = f"{request.developer_prompt}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
            },
        }

        max_tokens = request.max_tokens if request.max_tokens is not None else self.max_tokens
        if max_tokens and max_tokens > 0:
            payload["options"]["num_predict"] = max_tokens

        if request.system_prompt:
            payload["system"] = request.system_prompt

        if request.json_mode:
            payload["format"] = "json"

        return payload

    def _request_with_retry(self, method, path, payload=None, timeout_seconds=None):
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                return self._request(method, path, payload=payload, timeout_seconds=timeout_seconds or self.timeout)
            except AIError as exc:
                last_error = exc
                log_warning(
                    "Ollama request attempt failed",
                    provider=self.name,
                    attempt=attempt + 1,
                    retry_count=self.retry_count,
                    error=exc.to_dict(),
                )
                if not exc.retryable or attempt >= self.retry_count:
                    raise
                time.sleep(min(2**attempt, 5))

        raise last_error or unexpected("Ollama request failed.", provider=self.name)

    def _request(self, method, path, payload=None, timeout_seconds=None):
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds or self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                raise model_unavailable(f"Ollama model or endpoint unavailable: {detail}", provider=self.name) from exc
            raise provider_unavailable(f"Ollama returned HTTP {exc.code}: {detail}", provider=self.name) from exc
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), socket.timeout):
                raise timeout(
                    f"Ollama request timed out after {timeout_seconds or self.timeout} seconds.",
                    provider=self.name,
                ) from exc
            raise provider_unavailable(f"Cannot reach Ollama at {self.base_url}: {exc.reason}", provider=self.name) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise timeout(f"Ollama request timed out after {timeout_seconds or self.timeout} seconds.", provider=self.name) from exc
        except json.JSONDecodeError as exc:
            raise unexpected("Ollama returned invalid JSON.", provider=self.name) from exc

    def _stream_request(self, path, payload=None):
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for line in response:
                    if not line:
                        continue
                    yield json.loads(line.decode("utf-8"))
        except urllib.error.URLError as exc:
            raise provider_unavailable(f"Cannot stream from Ollama at {self.base_url}: {exc.reason}", provider=self.name) from exc
