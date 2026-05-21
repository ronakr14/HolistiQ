from abc import ABC, abstractmethod

from core.llm_tool.response import LLMResponse


class BaseAdapter(ABC):
    """
    Every provider must implement this interface.
    `complete()` always returns a normalized LLMResponse.
    """

    def __init__(self, model: str, **kwargs):
        self.model = model
        self.extra = kwargs  # provider-specific overrides (temperature, etc.)

    @abstractmethod
    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        """
        Send a completion request and return a normalized LLMResponse.

        Args:
            prompt:  User message.
            system:  Optional system prompt.
            **kwargs: Per-call overrides (temperature, max_tokens, etc.)
        """
        ...

    def _merge(self, base: dict, override: dict) -> dict:
        """Shallow-merge per-call overrides on top of adapter defaults."""
        return {**base, **override}
