from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    """
    Canonical response returned by every provider adapter.
    No field is ever missing — defaults ensure structural consistency.
    """

    text: str  # Main completion text
    provider: str  # e.g. "ollama", "openai"
    model: str  # Exact model name used
    route_tag: Optional[str] = None  # Tag that triggered routing (if any)
    prompt_tokens_api: int = 0
    completion_tokens_api: int = 0
    latency_ms: float = 0.0
    latency_ms_api: float = 0.0
    finish_reason: Optional[str] = None  # "stop", "length", etc.
    raw: Optional[dict] = field(default=None, repr=False)  # Full provider response
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "route_tag": self.route_tag,
            "usage_api": {
                "prompt_tokens": self.prompt_tokens_api,
                "completion_tokens": self.completion_tokens_api,
                "total_tokens": self.prompt_tokens_api + self.completion_tokens_api,
                "latency_ms_api": self.latency_ms_api,
            },
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
                "latency_ms": self.latency_ms,
            },
            "finish_reason": self.finish_reason,
        }
