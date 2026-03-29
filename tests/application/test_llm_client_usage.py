from __future__ import annotations

import json
from types import SimpleNamespace

from pydantic import BaseModel

from zenos.infrastructure.llm_client import LLMClient


class _SimpleSchema(BaseModel):
    answer: str


def _mk_response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage={"prompt_tokens": 12, "completion_tokens": 4},
    )


def test_chat_structured_gemini_includes_explicit_schema(monkeypatch):
    captured = {}

    def _fake_completion(**kwargs):
        captured.update(kwargs)
        return _mk_response({"answer": "ok"})

    monkeypatch.setattr("zenos.infrastructure.llm_client.litellm.completion", _fake_completion)

    client = LLMClient(model="gemini/gemini-2.5-flash-lite")
    out = client.chat_structured(
        messages=[{"role": "user", "content": "hi"}],
        response_schema=_SimpleSchema,
    )

    assert out.answer == "ok"
    assert isinstance(captured["response_format"], dict)
    assert captured["response_format"]["type"] == "json_object"
    assert "schema" in captured["response_format"]
    assert "guided_json" in captured
    assert captured["guided_json"]["type"] == "object"


def test_chat_structured_parses_code_fenced_json(monkeypatch):
    def _fake_completion(**kwargs):
        return _mk_response("```json\n{\"answer\":\"ok\"}\n```")

    monkeypatch.setattr("zenos.infrastructure.llm_client.litellm.completion", _fake_completion)

    client = LLMClient(model="gemini/gemini-2.5-flash-lite")
    out = client.chat_structured(
        messages=[{"role": "user", "content": "hi"}],
        response_schema=_SimpleSchema,
    )

    assert out.answer == "ok"


# ──────────────────────────────────────────────────────────────────────────────
# Schema injection into system prompt (Gemini fix)
# ──────────────────────────────────────────────────────────────────────────────

def test_gemini_system_prompt_contains_schema_json(monkeypatch):
    """Gemini branch: system prompt must include the full JSON schema string."""
    captured = {}

    def _fake_completion(**kwargs):
        captured.update(kwargs)
        return _mk_response({"answer": "ok"})

    monkeypatch.setattr("zenos.infrastructure.llm_client.litellm.completion", _fake_completion)

    client = LLMClient(model="gemini/gemini-2.5-flash-lite")
    client.chat_structured(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"},
        ],
        response_schema=_SimpleSchema,
    )

    system_msgs = [m for m in captured["messages"] if m["role"] == "system"]
    assert len(system_msgs) == 1
    system_content = system_msgs[0]["content"]
    assert "Output must be valid JSON matching this schema:" in system_content
    # The schema JSON itself should be embedded
    schema_json = json.dumps(_SimpleSchema.model_json_schema(), ensure_ascii=False)
    assert schema_json in system_content
    # Original prompt must still be present
    assert "You are a helpful assistant." in system_content


def test_gemini_creates_system_prompt_when_absent(monkeypatch):
    """Gemini branch: if no system message, inject one at the front with the schema."""
    captured = {}

    def _fake_completion(**kwargs):
        captured.update(kwargs)
        return _mk_response({"answer": "ok"})

    monkeypatch.setattr("zenos.infrastructure.llm_client.litellm.completion", _fake_completion)

    client = LLMClient(model="gemini/gemini-2.5-flash-lite")
    client.chat_structured(
        messages=[{"role": "user", "content": "hi"}],
        response_schema=_SimpleSchema,
    )

    system_msgs = [m for m in captured["messages"] if m["role"] == "system"]
    assert len(system_msgs) == 1
    assert "Output must be valid JSON matching this schema:" in system_msgs[0]["content"]
    # user message should still be present
    user_msgs = [m for m in captured["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 1


def test_gemini_does_not_mutate_original_messages(monkeypatch):
    """Gemini branch: original messages list must not be mutated."""
    def _fake_completion(**kwargs):
        return _mk_response({"answer": "ok"})

    monkeypatch.setattr("zenos.infrastructure.llm_client.litellm.completion", _fake_completion)

    original = [
        {"role": "system", "content": "original system"},
        {"role": "user", "content": "hi"},
    ]
    original_copy = [dict(m) for m in original]

    client = LLMClient(model="gemini/gemini-2.5-flash-lite")
    client.chat_structured(messages=original, response_schema=_SimpleSchema)

    assert original == original_copy, "Original messages list was mutated"


def test_non_gemini_model_does_not_inject_schema(monkeypatch):
    """Non-Gemini models must not have schema injected into system prompt."""
    captured = {}

    def _fake_completion(**kwargs):
        captured.update(kwargs)
        return _mk_response({"answer": "ok"})

    monkeypatch.setattr("zenos.infrastructure.llm_client.litellm.completion", _fake_completion)

    client = LLMClient(model="gpt-4o")
    client.chat_structured(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ],
        response_schema=_SimpleSchema,
    )

    system_msgs = [m for m in captured["messages"] if m["role"] == "system"]
    assert system_msgs[0]["content"] == "You are helpful."
