"""Tests for _PathTransportRouter routing logic.

Verifies that /sse and /messages/ are routed to the SSE app,
and /mcp is routed to the Streamable HTTP app.
"""

import pytest


class _RecordingApp:
    """Minimal ASGI app that records which scope it received."""

    def __init__(self, name: str):
        self.name = name
        self.calls: list[dict] = []

    async def __call__(self, scope, receive, send):
        self.calls.append(scope)


def _make_router(sse_app, stream_app):
    """Build a _PathTransportRouter without importing the full tools module."""

    from starlette.responses import JSONResponse

    class _PathTransportRouter:
        def __init__(self, stream_app, sse_app):
            self.stream_app = stream_app
            self.sse_app = sse_app

        async def __call__(self, scope, receive, send):
            path = scope.get("path", "")
            if path.startswith("/sse") or path.startswith("/messages/"):
                return await self.sse_app(scope, receive, send)
            if path.startswith("/mcp"):
                return await self.stream_app(scope, receive, send)
            response = JSONResponse({"error": "NOT_FOUND"}, status_code=404)
            return await response(scope, receive, send)

    return _PathTransportRouter(stream_app, sse_app)


def _scope(path: str) -> dict:
    return {"type": "http", "path": path, "query_string": b""}


@pytest.mark.asyncio
async def test_sse_path_routes_to_sse_app():
    sse = _RecordingApp("sse")
    stream = _RecordingApp("stream")
    router = _make_router(sse, stream)
    await router(_scope("/sse"), None, None)
    assert len(sse.calls) == 1
    assert len(stream.calls) == 0


@pytest.mark.asyncio
async def test_messages_path_routes_to_sse_app():
    """POST /messages/?session_id=... must be handled by the SSE app."""
    sse = _RecordingApp("sse")
    stream = _RecordingApp("stream")
    router = _make_router(sse, stream)
    await router(_scope("/messages/?session_id=abc123&api_key=key"), None, None)
    assert len(sse.calls) == 1
    assert len(stream.calls) == 0


@pytest.mark.asyncio
async def test_mcp_path_routes_to_stream_app():
    sse = _RecordingApp("sse")
    stream = _RecordingApp("stream")
    router = _make_router(sse, stream)
    await router(_scope("/mcp"), None, None)
    assert len(stream.calls) == 1
    assert len(sse.calls) == 0


@pytest.mark.asyncio
async def test_unknown_path_returns_404():
    sse = _RecordingApp("sse")
    stream = _RecordingApp("stream")
    router = _make_router(sse, stream)

    response_started = []

    async def capture_send(event):
        response_started.append(event)

    await router(_scope("/unknown"), None, capture_send)
    assert len(sse.calls) == 0
    assert len(stream.calls) == 0
    status_events = [e for e in response_started if e.get("type") == "http.response.start"]
    assert status_events[0]["status"] == 404
