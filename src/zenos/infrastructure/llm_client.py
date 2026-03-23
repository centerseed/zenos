"""LLM Client — thin wrapper around litellm for structured output.

Mirrors the interface of naru_agent's LiteLLMProvider.chat_structured()
without requiring naru_agent as a dependency (its pyproject.toml lacks
a build-system, so pip cannot install it).
"""

from __future__ import annotations

import os
from typing import Any

import litellm
from pydantic import BaseModel


class LLMClient:
    """Lightweight LLM client for structured (JSON) output."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        default_temperature: float = 0.1,
    ):
        self.model = model
        self.api_key = api_key
        self.default_temperature = default_temperature

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        """Call LLM with JSON output mode and parse into a Pydantic model."""
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "response_format": {"type": "json_object"},
            **kwargs,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        response = litellm.completion(**params)
        if not response.choices:
            raise ValueError("LLM returned empty choices list")
        content = response.choices[0].message.content
        return response_schema.model_validate_json(content)


def create_llm_client() -> LLMClient:
    """Create an LLMClient configured from environment variables."""
    return LLMClient(
        model=os.getenv("ZENOS_LLM_MODEL", "gemini/gemini-2.5-flash-lite"),
        api_key=os.getenv("GEMINI_API_KEY"),
        default_temperature=0.1,
    )
