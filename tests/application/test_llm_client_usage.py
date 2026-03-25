from __future__ import annotations

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
