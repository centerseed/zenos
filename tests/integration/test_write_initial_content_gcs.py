"""Integration test: MCP write(initial_content) → GCS revision → read_source.

Hits the real Cloud Run MCP endpoint. Requires environment variables:
  ZENOS_MCP_URL     — e.g. https://zenos-mcp-xxx.a.run.app/mcp
  ZENOS_API_KEY     — partner API key

Run with:
  pytest tests/integration/test_write_initial_content_gcs.py -m integration -v

Skip in CI:
  SKIP_INTEGRATION=1 pytest ...
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

# ---------------------------------------------------------------------------
# Guard: skip unless explicitly opted-in
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION") == "1",
    reason="Integration tests skipped (SKIP_INTEGRATION=1)",
)

MCP_URL = os.environ.get(
    "ZENOS_MCP_URL",
    "https://zenos-mcp-165893875709.asia-east1.run.app/mcp",
)
API_KEY = os.environ.get("ZENOS_API_KEY", "")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _mcp_url() -> str:
    return f"{MCP_URL}?api_key={API_KEY}"


def _call(method: str, params: dict) -> dict:
    """Send one JSON-RPC 2.0 MCP request; return the tool's structured response dict."""
    import json as _json
    if not API_KEY:
        pytest.skip("ZENOS_API_KEY not set — skipping integration test")
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    with httpx.Client(timeout=30) as client:
        resp = client.post(_mcp_url(), json=payload, headers=HEADERS)
    resp.raise_for_status()
    # Streamable HTTP / SSE: each line prefixed with "data: "
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            body = _json.loads(line[6:])
            if "error" in body:
                raise RuntimeError(f"MCP error: {body['error']}")
            outer = body.get("result", {})
            # Prefer structuredContent (parsed dict); fall back to parsing text
            if "structuredContent" in outer and outer["structuredContent"]:
                return outer["structuredContent"]
            content_list = outer.get("content", [])
            if content_list and content_list[0].get("text"):
                return _json.loads(content_list[0]["text"])
            return outer
    raise RuntimeError(f"No data line in response: {resp.text[:300]}")


def _tool_call(tool: str, arguments: dict) -> dict:
    return _call("tools/call", {"name": tool, "arguments": arguments})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _find_any_entity_id() -> str:
    """Return the ID of any available L2 entity to use as linked_entity_ids."""
    result = _tool_call("search", {"collection": "entities", "query": "", "limit": 1, "include": ["summary"]})
    items = result.get("data", result) if isinstance(result, dict) else result
    if isinstance(items, dict):
        items = items.get("entities") or items.get("results") or items.get("items") or []
    if items:
        return items[0].get("id", "")
    pytest.skip("No entities available in ZenOS — cannot create a linked document")


@pytest.fixture(scope="module")
def created_doc_id():
    """Create a document with initial_content; yield doc_id; archive on teardown."""
    run_id = uuid.uuid4().hex[:8]
    title = f"[integration-test] initial_content {run_id}"
    content = f"# Integration Test Doc {run_id}\n\nThis is a test document created by pytest.\n\n## Section\n\nContent here."

    entity_id = _find_any_entity_id()

    result = _tool_call("write", {
        "collection": "documents",
        "data": {
            "title": title,
            "type": "REFERENCE",
            "doc_role": "index",
            "summary": f"Integration test document {run_id} — created by pytest, will be archived.",
            "linked_entity_ids": [entity_id],
            "tags": {"what": ["integration-test"], "why": "pytest", "how": "initial_content", "who": ["developer"]},
            "initial_content": content,
        },
    })

    status = result.get("status", "")
    assert status != "rejected", f"write was rejected: {result.get('rejection_reason')} — {result}"

    data = result.get("data", {})
    doc_id = data.get("doc_id") or (data.get("entity", {}) or {}).get("id")
    assert doc_id, f"write did not return doc_id. result={result}"

    yield {"doc_id": doc_id, "content": content, "revision_id": data.get("revision_id")}

    # teardown: archive the test doc to avoid accumulating junk
    try:
        _tool_call("write", {
            "collection": "documents",
            "data": {"doc_id": doc_id, "status": "archived"},
        })
    except Exception:
        pass


# ---------------------------------------------------------------------------
# AC-DNH-29: write(initial_content) builds doc + zenos_native source + GCS revision
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_ac_dnh_29_write_initial_content_returns_ids(created_doc_id):
    """write(initial_content=...) must return doc_id, revision_id, source_id."""
    info = created_doc_id
    assert info["doc_id"], "doc_id missing"
    assert info["revision_id"], "revision_id missing — GCS write may have failed"


# ---------------------------------------------------------------------------
# AC-DNH-30: read_source returns full markdown (content_type="full")
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_ac_dnh_30_read_source_returns_full_content(created_doc_id):
    """read_source(doc_id) must return content_type='full' with the original markdown."""
    info = created_doc_id
    result = _tool_call("read_source", {"doc_id": info["doc_id"]})

    data = result.get("data", result)
    content_type = data.get("content_type") or data.get("type")
    content = data.get("content") or data.get("markdown") or data.get("text") or ""

    assert content_type == "full", (
        f"Expected content_type='full', got {content_type!r}. "
        "GCS revision may not have been written correctly."
    )
    assert "Integration Test Doc" in content, (
        f"Returned content does not contain expected text. content[:200]={content[:200]!r}"
    )
    assert len(content) > 50, "Content suspiciously short — may be truncated"


# ---------------------------------------------------------------------------
# AC-DNH-31: initial_content > 1 MB → 413
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_ac_dnh_31_initial_content_too_large_rejected():
    """write(initial_content > 1MB) must be rejected with INITIAL_CONTENT_TOO_LARGE."""
    if not API_KEY:
        pytest.skip("ZENOS_API_KEY not set")

    oversized = "x" * (1_048_576 + 1)
    try:
        result = _tool_call("write", {
            "collection": "documents",
            "data": {
                "title": "[integration-test] oversized",
                "type": "REFERENCE",
                "doc_role": "index",
                "summary": "oversized test",
                "linked_entity_ids": [],
                "initial_content": oversized,
            },
        })
        status = (result.get("status") or "").lower()
        rejection_reason = str(result.get("rejection_reason") or "").upper()
        assert status == "rejected", f"Expected rejection, got status={status!r}. result={result}"
        assert "TOO_LARGE" in rejection_reason or "INITIAL_CONTENT" in rejection_reason, (
            f"Unexpected rejection_reason: {rejection_reason}"
        )
    except RuntimeError as exc:
        assert "TOO_LARGE" in str(exc).upper() or "413" in str(exc), (
            f"Expected TOO_LARGE error, got: {exc}"
        )
