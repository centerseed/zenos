"""Tests for SseApiKeyPropagator ASGI middleware.

Verifies that the SSE endpoint URL in the response body is patched to include
the api_key query param when the original request carries api_key, and is left
unchanged otherwise.
"""

import pytest

from zenos.interface.mcp import SseApiKeyPropagator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scope(query_string: bytes = b"", scope_type: str = "http") -> dict:
    return {
        "type": scope_type,
        "query_string": query_string,
        "path": "/sse",
    }


class _CapturingApp:
    """Fake inner ASGI app that records events passed via send."""

    def __init__(self, events_to_emit: list[dict]):
        self._events = events_to_emit
        self.received_send_calls: list[dict] = []

    async def __call__(self, scope, receive, send):
        for event in self._events:
            await send(event)


# ---------------------------------------------------------------------------
# P0: with api_key — endpoint URL is patched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patches_endpoint_url_when_api_key_present():
    """SSE endpoint event URL gains &api_key=... when api_key is in query string."""
    original_body = b"event: endpoint\ndata: /messages/?session_id=abc-123\n\n"
    inner_app = _CapturingApp(
        [{"type": "http.response.body", "body": original_body, "more_body": False}]
    )
    propagator = SseApiKeyPropagator(inner_app)

    sent_events: list[dict] = []

    async def capture_send(event):
        sent_events.append(event)

    scope = _make_scope(query_string=b"api_key=my-secret-key")
    await propagator(scope, None, capture_send)

    assert len(sent_events) == 1
    body_text = sent_events[0]["body"].decode("utf-8")
    assert "&api_key=my-secret-key" in body_text
    assert "session_id=abc-123" in body_text


# ---------------------------------------------------------------------------
# P0: without api_key — pass-through, body not modified
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passthrough_when_no_api_key():
    """Response body is not modified when no api_key query param is present."""
    original_body = b"event: endpoint\ndata: /messages/?session_id=abc-123\n\n"
    inner_app = _CapturingApp(
        [{"type": "http.response.body", "body": original_body, "more_body": False}]
    )
    propagator = SseApiKeyPropagator(inner_app)

    sent_events: list[dict] = []

    async def capture_send(event):
        sent_events.append(event)

    scope = _make_scope(query_string=b"")
    await propagator(scope, None, capture_send)

    assert len(sent_events) == 1
    assert sent_events[0]["body"] == original_body


# ---------------------------------------------------------------------------
# P0: non-http scope type — pass-through without touching send
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passthrough_for_non_http_scope():
    """Non-http scope types (e.g. websocket) bypass the propagator entirely."""
    original_body = b"data: /messages/?session_id=abc-123\n\n"
    inner_app = _CapturingApp(
        [{"type": "http.response.body", "body": original_body, "more_body": False}]
    )
    propagator = SseApiKeyPropagator(inner_app)

    sent_events: list[dict] = []

    async def capture_send(event):
        sent_events.append(event)

    scope = _make_scope(query_string=b"api_key=my-secret-key", scope_type="websocket")
    await propagator(scope, None, capture_send)

    # Inner app uses its own send; our capture_send is NOT passed in for non-http
    # scopes, so sent_events remains empty (inner app's send is the real one).
    # We verify that propagator called the inner app directly without wrapping.
    # Since _CapturingApp sends to whatever send is passed, and we passed capture_send,
    # but for non-http we delegate to inner app with the original send, which in this
    # test IS capture_send. The body must NOT be patched.
    assert len(sent_events) == 1
    assert sent_events[0]["body"] == original_body


# ---------------------------------------------------------------------------
# Edge case: regex only captures up to first & (session_id without extras)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regex_only_matches_session_id_portion():
    """The regex pattern captures session_id=[^\\s&]+ which stops at the first &.

    This verifies the regex correctly matches only the session_id value portion,
    not beyond it. In normal usage the SSE body has bare session_id with no
    subsequent query params, so double-injection cannot occur.
    """
    original_body = b"event: endpoint\ndata: /messages/?session_id=abc-123\n\n"
    inner_app = _CapturingApp(
        [{"type": "http.response.body", "body": original_body, "more_body": False}]
    )
    propagator = SseApiKeyPropagator(inner_app)

    sent_events: list[dict] = []

    async def capture_send(event):
        sent_events.append(event)

    scope = _make_scope(query_string=b"api_key=testkey42")
    await propagator(scope, None, capture_send)

    body_text = sent_events[0]["body"].decode("utf-8")
    # api_key appended exactly once (no pre-existing &api_key in the body)
    assert body_text.count("api_key=testkey42") == 1
    assert "session_id=abc-123&api_key=testkey42" in body_text


# ---------------------------------------------------------------------------
# Edge case: non-body events (headers) are forwarded unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_body_events_forwarded_unchanged():
    """http.response.start (headers) events pass through without modification."""
    header_event = {
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/event-stream")],
    }
    body_event = {
        "type": "http.response.body",
        "body": b"data: /messages/?session_id=xyz\n\n",
        "more_body": False,
    }
    inner_app = _CapturingApp([header_event, body_event])
    propagator = SseApiKeyPropagator(inner_app)

    sent_events: list[dict] = []

    async def capture_send(event):
        sent_events.append(event)

    scope = _make_scope(query_string=b"api_key=testkey")
    await propagator(scope, None, capture_send)

    assert sent_events[0] == header_event
    body_text = sent_events[1]["body"].decode("utf-8")
    assert "&api_key=testkey" in body_text


@pytest.mark.asyncio
async def test_propagates_project_query_param_when_present():
    """SSE endpoint URL should preserve project query param across /messages hop."""
    original_body = b"event: endpoint\ndata: /messages/?session_id=abc-123\n\n"
    inner_app = _CapturingApp(
        [{"type": "http.response.body", "body": original_body, "more_body": False}]
    )
    propagator = SseApiKeyPropagator(inner_app)

    sent_events: list[dict] = []

    async def capture_send(event):
        sent_events.append(event)

    scope = _make_scope(query_string=b"api_key=testkey&project=Paceriz")
    await propagator(scope, None, capture_send)

    body_text = sent_events[0]["body"].decode("utf-8")
    assert "&api_key=testkey" in body_text
    assert "&project=paceriz" in body_text
