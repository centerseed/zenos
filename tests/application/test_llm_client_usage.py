from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from zenos.infrastructure.llm_client import LLMClient


class _Resp(BaseModel):
    ok: bool


def _make_response(content: str, usage: dict[str, int] | None):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


def test_chat_structured_records_usage_tokens():
    client = LLMClient(model="gemini/test")
    with patch("zenos.infrastructure.llm_client.litellm.completion") as completion:
        completion.return_value = _make_response('{"ok": true}', {"prompt_tokens": 12, "completion_tokens": 7})
        parsed = client.chat_structured(
            messages=[{"role": "user", "content": "ping"}],
            response_schema=_Resp,
        )
    assert parsed.ok is True
    assert client.last_usage == {"model": "gemini/test", "tokens_in": 12, "tokens_out": 7}


def test_consume_last_usage_clears_state():
    client = LLMClient(model="gemini/test")
    with patch("zenos.infrastructure.llm_client.litellm.completion") as completion:
        completion.return_value = _make_response('{"ok": true}', {"prompt_tokens": 3, "completion_tokens": 1})
        client.chat_structured(
            messages=[{"role": "user", "content": "ping"}],
            response_schema=_Resp,
        )
    usage = client.consume_last_usage()
    assert usage == {"model": "gemini/test", "tokens_in": 3, "tokens_out": 1}
    assert client.consume_last_usage() is None
