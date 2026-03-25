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
        self.last_usage: dict[str, int | str] | None = None

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int]:
        """Extract prompt/completion token usage from a LiteLLM response."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"tokens_in": 0, "tokens_out": 0}
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
            completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
        else:
            prompt = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0))
            completion = getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0))
        return {"tokens_in": int(prompt or 0), "tokens_out": int(completion or 0)}

    def consume_last_usage(self) -> dict[str, int | str] | None:
        """Return and clear the latest usage metadata."""
        usage = self.last_usage
        self.last_usage = None
        return usage

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

        self.last_usage = None
        response = litellm.completion(**params)
        usage = self._extract_usage(response)
        self.last_usage = {
            "model": self.model,
            "tokens_in": usage["tokens_in"],
            "tokens_out": usage["tokens_out"],
        }
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
