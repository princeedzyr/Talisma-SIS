from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIRequest:
    user_prompt: str
    system_prompt: str = ""
    developer_prompt: str = ""
    context: dict = field(default_factory=dict)
    json_mode: bool = False
    stream: bool = False
    correlation_id: str = None
    max_tokens: int = None
    timeout_seconds: int = None


@dataclass
class AIResponse:
    success: bool
    response_text: str = ""
    provider: str = None
    model: str = None
    latency: float = 0.0
    chunks: list = field(default_factory=list)
    error: dict = field(default_factory=dict)
    raw_response: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "success": self.success,
            "response_text": self.response_text,
            "provider": self.provider,
            "model": self.model,
            "latency": self.latency,
            "chunks": self.chunks,
            "error": self.error,
            "raw_response": self.raw_response,
        }


@dataclass(frozen=True)
class AIChunk:
    text: str
    index: int
    done: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "text": self.text,
            "index": self.index,
            "done": self.done,
            "metadata": self.metadata,
        }
