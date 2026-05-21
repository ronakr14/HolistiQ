"""
LLMRouter: main entry point.

- Loads config once at init.
- Routes queries to providers via keyword/tag rules defined in YAML.
- Falls back to default_provider if no rule matches.
- Returns a normalized LLMResponse from whichever adapter is used.
"""

from __future__ import annotations

import re
from typing import Optional

from core.llm_tool.base import BaseAdapter
from core.llm_tool.response import LLMResponse
from core.loaders.config_loader import validate_load_config
from custom_logger.logging_util import get_logger

logger = get_logger(__name__)

# Provider map removed; builders are looked up dynamically by name.


class LLMRouter:
    """
    Usage:
        router = LLMRouter("llm_config.yaml")
        response = router.complete("Summarize this SQL query: SELECT ...")
        print(response.text)
        print(response.to_dict())
    """

    def __init__(self, config_path: str):
        self.cfg = validate_load_config(config_path)
        self._adapter_cache: dict[str, BaseAdapter] = {}

    def complete(
        self,
        prompt: str,
        system: str = "",
        provider: Optional[str] = None,  # force a specific provider
        **kwargs,
    ) -> LLMResponse:
        """
        Route prompt → adapter → normalized LLMResponse.

        Provider resolution order:
            1. `provider` argument (explicit override)
            2. First matching routing rule in config
            3. `default_provider` from config
        """
        tag, resolved_provider = self._resolve_provider(prompt, provider)
        adapter = self._get_adapter(resolved_provider)
        logger.info(f"transferring to {adapter.__class__.__name__}...")
        response = adapter.complete(prompt, system=system, **kwargs)
        response.route_tag = tag
        return response

    def providers(self) -> list[str]:
        """List all configured provider names."""
        logger.debug("fetching available providers...")
        return list(self.cfg["providers"].keys())

    def routing_rules(self) -> list[dict]:
        """Return the routing rules as defined in config."""
        logger.debug("fetching routing rules...")
        return self.cfg.get("routing", [])

    def _resolve_provider(
        self, prompt: str, forced: Optional[str]
    ) -> tuple[Optional[str], str]:
        """
        Returns (matched_tag, provider_name).
        tag is None when falling back to default.
        """
        logger.debug("resolving provider...")
        if forced:
            logger.info(f"forced provider: {forced}")
            if forced not in self.cfg["providers"]:
                raise ValueError(
                    f"Provider '{forced}' not found in config. "
                    f"Available: {list(self.cfg['providers'].keys())}"
                )
            return None, forced

        prompt_lower = prompt.lower()
        logger.debug("routing based on prompt...")
        for rule in self.cfg.get("routing", []):
            tag = rule.get("tag", "")
            keywords = rule.get("keywords", [])
            provider = rule.get("provider")

            if not provider or provider not in self.cfg["providers"]:
                continue  # skip misconfigured rules silently

            for kw in keywords:
                pattern = rf"\b{re.escape(kw.lower())}\b"
                if re.search(pattern, prompt_lower):
                    return tag, provider

        return None, self.cfg["default_provider"]

    def _get_adapter(self, provider: str) -> BaseAdapter:
        """Return a cached adapter instance for the given provider."""
        logger.debug("fetching adapter...")
        if provider not in self._adapter_cache:
            self._adapter_cache[provider] = self._build_adapter(provider)
        return self._adapter_cache[provider]

    def _build_adapter(self, provider: str) -> BaseAdapter:
        logger.debug("building adapter...")
        builder = getattr(self, f"_build_{provider}", None)
        if builder is None:
            raise ValueError(
                f"Unknown provider '{provider}'. Supported: {list(self.cfg['providers'].keys())}"
            )
        return builder()

    def _provider_cfg(self, name: str) -> dict:
        logger.debug("fetching provider config...")
        return self.cfg["providers"][name]

    def _build_ollama(self) -> "OllamaAdapter":  # type: ignore  # noqa: F821
        from core.llm_tool.adapter.ollama import OllamaAdapter

        logger.debug("building ollama adapter...")
        c = self._provider_cfg("ollama")
        return OllamaAdapter(
            model=c["model"],
            # base_url=c.get("base_url", "http://localhost:11434"),
            **c.get("options", {}),
        )

    # def _build_openai(self) -> "OpenAIAdapter":  # noqa: F821
    #     from .providers.openai import OpenAIAdapter
    #     c = self._provider_cfg("openai")
    #     return OpenAIAdapter(
    #         model=c["model"],
    #         api_key=c["api_key"],
    #         **c.get("options", {}),
    #     )

    # def _build_anthropic(self) -> "AnthropicAdapter":  # noqa: F821
    #     from .providers.anthropic import AnthropicAdapter
    #     c = self._provider_cfg("anthropic")
    #     return AnthropicAdapter(
    #         model=c["model"],
    #         api_key=c["api_key"],
    #         **c.get("options", {}),
    #     )

    # def _build_gemini(self) -> "GeminiAdapter":  # noqa: F821
    #     from .providers.gemini import GeminiAdapter
    #     c = self._provider_cfg("gemini")
    #     return GeminiAdapter(
    #         model=c["model"],
    #         api_key=c["api_key"],
    #         **c.get("options", {}),
    #     )

    # def _build_openrouter(self) -> "OpenRouterAdapter":  # noqa: F821
    #     from .providers.openrouter import OpenRouterAdapter
    #     c = self._provider_cfg("openrouter")
    #     return OpenRouterAdapter(
    #         model=c["model"],
    #         api_key=c["api_key"],
    #         site_url=c.get("site_url", ""),
    #         app_name=c.get("app_name", ""),
    #         **c.get("options", {}),
    #     )
