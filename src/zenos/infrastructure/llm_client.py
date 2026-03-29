"""LLM Client — thin wrapper around litellm for structured output.

Mirrors the interface of naru_agent's LiteLLMProvider.chat_structured()
without requiring naru_agent as a dependency (its pyproject.toml lacks
a build-system, so pip cannot install it).
"""

from __future__ import annotations

import json
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
        schema = response_schema.model_json_schema()
        response_format: Any = response_schema
        if "gemini" in self.model.lower():
            # Gemini via LiteLLM may degrade class-based response_format into bare
            # json_object. Explicit schema improves structured-output reliability.
            response_format = {
                "type": "json_object",
                "schema": schema,
            }
            messages = self._inject_schema_into_system_prompt(messages, schema)

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "response_format": response_format,
            "guided_json": schema,
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
        return self._parse_structured_content(content, response_schema)

    @staticmethod
    def _inject_schema_into_system_prompt(
        messages: list[dict[str, str]],
        schema: dict,
    ) -> list[dict[str, str]]:
        """Return a copy of messages with the JSON schema appended to the system prompt.

        If no system message exists, one is inserted at the front.
        The original messages list is never mutated.
        """
        schema_suffix = (
            "\n\nOutput must be valid JSON matching this schema:\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        messages = list(messages)
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                messages[i] = {**msg, "content": msg["content"] + schema_suffix}
                return messages
        messages.insert(0, {"role": "system", "content": schema_suffix.lstrip()})
        return messages

    @staticmethod
    def _parse_structured_content(content: Any, response_schema: type[BaseModel]) -> BaseModel:
        """Parse LLM content robustly into the target schema."""
        if isinstance(content, dict):
            return response_schema.model_validate(content)
        if isinstance(content, list):
            return response_schema.model_validate(content)
        if not isinstance(content, str):
            raise ValueError(f"Unsupported structured content type: {type(content)!r}")

        try:
            return response_schema.model_validate_json(content)
        except Exception:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()
            parsed = json.loads(cleaned)
            return response_schema.model_validate(parsed)


def create_llm_client() -> LLMClient:
    """Create an LLMClient configured from environment variables."""
    return LLMClient(
        model=os.getenv("ZENOS_LLM_MODEL", "gemini/gemini-2.5-flash-lite"),
        api_key=os.getenv("GEMINI_API_KEY"),
        default_temperature=0.1,
    )
