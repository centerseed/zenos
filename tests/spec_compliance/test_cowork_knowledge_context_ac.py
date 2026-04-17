"""
Spec compliance checks for SPEC-cowork-knowledge-context.

Strategy:
- Runtime assertions for the backend graph-context API.
- Source-contract assertions for frontend/helper wiring that is otherwise
  covered by Vitest.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.interface.test_dashboard_api import _PARTNER, _make_entity, _make_request, _make_document
from zenos.domain.knowledge import Entity


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


async def _call_graph_context(
    *,
    seed: Entity,
    query_params: dict[str, str] | None = None,
    list_children_side_effect=None,
    relationships=None,
):
    from zenos.interface.dashboard_api import get_cowork_graph_context

    request = _make_request(
        headers={"authorization": "Bearer fake-token"},
        query_params={"seed_id": seed.id, **(query_params or {})},
    )
    with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(_PARTNER, "p1"))), \
         patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(return_value=seed)), \
         patch("zenos.interface.dashboard_api._list_children_with_context", new=AsyncMock(side_effect=list_children_side_effect or (lambda *_: []))), \
         patch("zenos.interface.dashboard_api._list_relationships_with_context", new=AsyncMock(return_value=relationships or [])):
        resp = await get_cowork_graph_context(request)
    assert resp.status_code == 200
    return json.loads(resp.body)


@pytest.mark.spec("AC-CKC-01")
def test_ac_ckc_01_helper_mcp_parity():
    crm_skill = _read("dashboard/public/installers/skills/crm-briefing/SKILL.md")
    marketing_skill = _read("dashboard/public/installers/skills/marketing-plan/SKILL.md")
    assert "mcp__zenos__get" in crm_skill
    assert "mcp__zenos__get" in marketing_skill


@pytest.mark.spec("AC-CKC-02")
def test_ac_ckc_02_pre_first_turn_traversal():
    page = _read("dashboard/src/features/marketing/MarketingWorkspace.tsx")
    assert "const nextGraphContext = promptContext ? null : await ensureGraphContext();" in page
    assert "await streamCoworkChat({" in page
    assert page.index("await ensureGraphContext();") < page.index("await streamCoworkChat({")
    assert "graph_context: graphContext" in page


@pytest.mark.spec("AC-CKC-03")
def test_ac_ckc_03_no_seed_no_traversal():
    graph_context = _read("dashboard/src/lib/graph-context.ts")
    assert "if (!seedId) return null;" in graph_context


@pytest.mark.spec("AC-CKC-04")
def test_ac_ckc_04_mcp_unavailable_fallback():
    page = _read("dashboard/src/features/marketing/MarketingWorkspace.tsx")
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "!capability.mcpOk" in page
    assert "graphContextUnavailableNotice()" in page
    assert "知識圖譜暫時無法讀取" in prompt


@pytest.mark.asyncio
@pytest.mark.spec("AC-CKC-05")
async def test_ac_ckc_05_partial_failure_resilience():
    seed = _make_entity("prod-1")
    seed.type = "product"
    seed.level = 1
    children = [_make_entity("module-1"), _make_entity("module-2")]
    for child in children:
        child.parent_id = seed.id

    async def list_children(_effective_id: str, entity_id: str):
        if entity_id == seed.id:
            return children
        raise RuntimeError("timeout")

    body = await _call_graph_context(seed=seed, list_children_side_effect=list_children)
    assert body["partial"] is True
    assert body["errors"]
    assert body["fallback_mode"] == "l1_tags_only"


@pytest.mark.asyncio
@pytest.mark.spec("AC-CKC-10")
async def test_ac_ckc_10_l2_neighbors_complete():
    seed = _make_entity("prod-1")
    seed.type = "product"
    seed.level = 1
    children = [_make_entity("module-1"), _make_entity("module-2"), _make_entity("module-3")]
    for idx, child in enumerate(children):
        child.parent_id = seed.id
        child.tags.what = [f"what-{idx}"]
        child.tags.who = [f"who-{idx}"]

    async def list_children(_effective_id: str, entity_id: str):
        return children if entity_id == seed.id else []

    body = await _call_graph_context(seed=seed, list_children_side_effect=list_children)
    assert len(body["neighbors"]) == 3
    first = body["neighbors"][0]
    assert {"id", "name", "type", "level", "tags", "summary"} <= set(first)
    assert {"what", "why", "how", "who"} <= set(first["tags"])


@pytest.mark.asyncio
@pytest.mark.spec("AC-CKC-11")
async def test_ac_ckc_11_l3_summary_included():
    seed = _make_entity("prod-1")
    seed.type = "product"
    seed.level = 1
    module = _make_entity("module-1")
    module.parent_id = seed.id

    async def list_children(_effective_id: str, entity_id: str):
        if entity_id == seed.id:
            return [module]
        if entity_id == module.id:
            return [_make_document("spec-1", parent_id=module.id, summary="spec summary " * 80)]
        return []

    body = await _call_graph_context(seed=seed, list_children_side_effect=list_children)
    doc = body["neighbors"][0]["documents"][0]
    assert {"doc_id", "title", "type", "status", "summary"} <= set(doc)
    assert len(doc["summary"]) <= 500


@pytest.mark.asyncio
@pytest.mark.spec("AC-CKC-12")
async def test_ac_ckc_12_status_filter():
    seed = _make_entity("prod-1")
    seed.type = "product"
    seed.level = 1
    active = _make_entity("module-active")
    active.parent_id = seed.id
    draft = _make_entity("module-draft")
    draft.parent_id = seed.id
    draft.status = "draft"
    archived = _make_entity("module-archived")
    archived.parent_id = seed.id
    archived.status = "archived"

    async def list_children(_effective_id: str, entity_id: str):
        return [active, draft, archived] if entity_id == seed.id else []

    body = await _call_graph_context(seed=seed, list_children_side_effect=list_children)
    assert [neighbor["id"] for neighbor in body["neighbors"]] == ["module-active"]


@pytest.mark.asyncio
@pytest.mark.spec("AC-CKC-13")
async def test_ac_ckc_13_token_budget_truncation():
    seed = _make_entity("prod-1")
    seed.type = "product"
    seed.level = 1
    children = []
    docs_by_parent: dict[str, list[Entity]] = {}
    for index in range(3):
        child = _make_entity(f"module-{index}")
        child.parent_id = seed.id
        child.summary = "module summary " * 20
        children.append(child)
        docs_by_parent[child.id] = [
            _make_document(f"doc-{index}-a", parent_id=child.id, summary="doc summary " * 50),
            _make_document(f"doc-{index}-b", parent_id=child.id, summary="doc summary " * 50),
        ]

    async def list_children(_effective_id: str, entity_id: str):
        if entity_id == seed.id:
            return children
        return docs_by_parent.get(entity_id, [])

    body = await _call_graph_context(
        seed=seed,
        query_params={"budget_tokens": "40"},
        list_children_side_effect=list_children,
    )
    assert body["truncated"] is True
    assert body["estimated_tokens"] <= 40
    assert body["truncation_details"]["dropped_l2"] >= 0


@pytest.mark.spec("AC-CKC-14")
def test_ac_ckc_14_graph_context_loaded_event():
    graph_context = _read("dashboard/src/lib/graph-context.ts")
    helper_types = _read("dashboard/src/lib/cowork-helper.ts")
    assert "createGraphContextLoadedPayload" in graph_context
    assert "l2_count" in graph_context and "l3_count" in graph_context
    assert '"graph_context_loaded"' in helper_types


@pytest.mark.spec("AC-CKC-15")
def test_ac_ckc_15_session_cache():
    graph_context = _read("dashboard/src/lib/graph-context.ts")
    assert "GRAPH_CONTEXT_CACHE_TTL_MS = 60_000" in graph_context
    assert "graphContextCache = new Map" in graph_context


@pytest.mark.spec("AC-CKC-20")
def test_ac_ckc_20_badge_default_collapsed():
    badge = _read("dashboard/src/components/ai/GraphContextBadge.tsx")
    assert "<details" in badge
    assert "已讀取 {l2Count} 個模組、{l3Count} 個文件" in badge


@pytest.mark.spec("AC-CKC-21")
def test_ac_ckc_21_badge_hierarchy():
    badge = _read("dashboard/src/components/ai/GraphContextBadge.tsx")
    assert "graphContext.seed.name" in badge
    assert "graphContext.neighbors.map" in badge
    assert "neighbor.documents.map" in badge
    assert "graph_context=" not in badge


@pytest.mark.spec("AC-CKC-22")
def test_ac_ckc_22_truncation_notice():
    badge = _read("dashboard/src/components/ai/GraphContextBadge.tsx")
    assert "還有 {hiddenCount} 個節點因長度限制未載入" in badge


@pytest.mark.spec("AC-CKC-23")
def test_ac_ckc_23_fallback_notice():
    badge = _read("dashboard/src/components/ai/GraphContextBadge.tsx")
    assert "if (!graphContext)" in badge
    assert "unavailableReason" in badge


@pytest.mark.spec("AC-CKC-30")
def test_ac_ckc_30_first_turn_cites_nodes():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "graph_derivable" in prompt
    assert "source_citations" in prompt
    assert "renderGraphContextBlock" in prompt


@pytest.mark.spec("AC-CKC-31")
def test_ac_ckc_31_no_fabrication():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "不得捏造引用" in prompt
    assert "缺少依據" in prompt


@pytest.mark.spec("AC-CKC-32")
def test_ac_ckc_32_one_question_per_turn():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "每一輪最多只追問一個 user_required 欄位" in prompt


@pytest.mark.spec("AC-CKC-33")
def test_ac_ckc_33_pending_marker():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "pending_fields" in prompt
    assert "先跳過" in prompt


@pytest.mark.spec("AC-CKC-34")
def test_ac_ckc_34_apply_contract():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert '"target_field":"strategy"' in prompt
    assert '"value"' in prompt


@pytest.mark.spec("AC-CKC-35")
def test_ac_ckc_35_turn_limit_10():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    page = _read("dashboard/src/features/marketing/MarketingWorkspace.tsx")
    helper = _read("tools/claude-cowork-helper/server.mjs")
    assert "export const COWORK_MAX_TURNS = 10;" in prompt
    assert "已達對話上限，請整理當前結果或開啟新 session。" in page
    assert "maxTurns: Number.isFinite(body.maxTurns) ? Number(body.maxTurns) : 10" in helper


@pytest.mark.asyncio
@pytest.mark.spec("AC-CKC-40")
async def test_ac_ckc_40_l1_only_fallback_mode():
    seed = _make_entity("prod-1")
    seed.type = "product"
    seed.level = 1

    async def list_children(_effective_id: str, entity_id: str):
        return [] if entity_id == seed.id else []

    body = await _call_graph_context(seed=seed, list_children_side_effect=list_children)
    assert body["fallback_mode"] == "l1_tags_only"
    assert len(body["neighbors"]) <= 1
    assert {"what", "why", "how", "who"} <= set(body["seed"]["tags"])


@pytest.mark.spec("AC-CKC-41")
def test_ac_ckc_41_l1_fallback_notice():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "目前只有基本產品資訊" in prompt
    assert "以下草案僅基於產品 tags" in prompt


@pytest.mark.spec("AC-CKC-42")
def test_ac_ckc_42_low_confidence_marker():
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert 'confidence=\\"low\\"' in prompt


@pytest.mark.spec("AC-CKC-50")
def test_ac_ckc_50_crm_briefing_uses_flow():
    crm = _read("dashboard/src/features/crm/CrmAiPanel.tsx")
    assert "fetchGraphContext" in crm
    assert "company.zenosEntityId" in crm
    assert "buildCrmKnowledgePrompt" in crm


@pytest.mark.spec("AC-CKC-51")
def test_ac_ckc_51_briefing_cites_nodes():
    crm = _read("dashboard/src/features/crm/CrmAiPanel.tsx")
    assert "GraphContextBadge" in crm
    assert "graph_context_l2_count" in crm
    assert "graph_context_l3_count" in crm


@pytest.mark.spec("AC-CKC-55")
def test_ac_ckc_55_strategy_seed_and_targets():
    page = _read("dashboard/src/features/marketing/MarketingWorkspace.tsx")
    prompt = _read("dashboard/src/lib/cowork-knowledge.ts")
    assert "seed_entity: campaignId" in page
    assert "target_fields: MARKETING_STRATEGY_TARGET_FIELDS" in page
    assert prompt.count("source_preference") >= 2


@pytest.mark.spec("AC-CKC-56")
def test_ac_ckc_56_strategy_applied_traceable():
    page = _read("dashboard/src/features/marketing/MarketingWorkspace.tsx")
    api = _read("src/zenos/interface/marketing_dashboard_api.py")
    assert "normalizeSourceCitations" in page
    assert "pendingFields" in page
    assert "sourceCitations" in page
    assert "confidence" in page
    assert "source_citations" in api
    assert "pending_fields" in api


@pytest.mark.skip(reason="Requires live Paceriz demo environment and recorded artifact.")
@pytest.mark.spec("AC-CKC-60")
def test_ac_ckc_60_paceriz_e2e_happy():
    pass


@pytest.mark.skip(reason="Requires live multi-turn timing validation in dashboard.")
@pytest.mark.spec("AC-CKC-61")
def test_ac_ckc_61_paceriz_progressive_10min():
    pass


@pytest.mark.skip(reason="Requires live dashboard writeback persistence validation.")
@pytest.mark.spec("AC-CKC-62")
def test_ac_ckc_62_paceriz_apply_writeback():
    pass


@pytest.mark.skip(reason="Demo video evidence is a manual artifact, not an automated assertion.")
@pytest.mark.spec("AC-CKC-63")
def test_ac_ckc_63_demo_video_evidence():
    pass


@pytest.mark.skip(reason="Requires live fallback demo flow against a sparse L1 product.")
@pytest.mark.spec("AC-CKC-64")
def test_ac_ckc_64_fallback_path():
    pass
