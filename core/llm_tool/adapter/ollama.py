import time

import ollama

from core.llm_tool.base import BaseAdapter
from core.llm_tool.response import LLMResponse
from core.llm_tool.token_counter import count_tokens
from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


class OllamaAdapter(BaseAdapter):
    """
    Adapter for locally running Ollama.
    No API key needed — uses HTTP endpoint from config.
    """

    def __init__(self, model: str, **kwargs):
        super().__init__(model, **kwargs)

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        cal_tokens = kwargs.pop("cal_tokens", False)
        messages = []
        if system:
            logger.info("adding system prompt")
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options = self._merge(self.extra, kwargs)

        t0 = time.perf_counter()

        response = ollama.chat(model=self.model, messages=messages, options=options)
        logger.debug("ollama response generated")

        latency = (time.perf_counter() - t0) * 1000

        if cal_tokens:
            prompt_tokens = count_tokens(prompt, self.model, "transformer")
            completion_tokens = count_tokens(
                response.message.content or "", self.model, "transformer"
            )

        return LLMResponse(
            text=response.message.content or "",
            provider="ollama",
            model=self.model,
            prompt_tokens_api=response.prompt_eval_count or 0,
            completion_tokens_api=response.eval_count or 0,
            latency_ms=round(latency, 2),
            latency_ms_api=round(response.total_duration / 1000000, 2),
            finish_reason=response.done_reason or None,
            raw=response,
            prompt_tokens=prompt_tokens if cal_tokens else 0,
            completion_tokens=completion_tokens if cal_tokens else 0,
        )
