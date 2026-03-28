"""E2E validation -- Naruvia (Paceriz) ontology import via application layer.

Connects to Firestore (emulator or real zenos-naruvia project) and walks
through the complete ontology lifecycle:
  Step 1: Build the Paceriz ontology
  Step 2: Consumer-side verification
  Step 3: Governance-side verification

Data is intentionally NOT cleaned up.
"""

from __future__ import annotations

import re

import pytest
import pytest_asyncio

from zenos.application.governance_service import GovernanceService
from zenos.application.ontology_service import OntologyService
from zenos.infrastructure.firestore_repo import (
    FirestoreBlindspotRepository,
    FirestoreDocumentRepository,
    FirestoreEntityRepository,
    FirestoreProtocolRepository,
    FirestoreRelationshipRepository,
    get_db,
)

# Use a single event loop for the entire module so that session-scoped
# async fixtures and sequential tests share the same Firestore client.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(scope="module", autouse=True)
def _require_firestore_client():
    """Skip this module when Firestore client is mocked/stubbed by other tests."""
    db = get_db()
    if not hasattr(db, "collection"):
        pytest.skip("Firestore client not available for e2e integration tests")


# ------------------------------------------------------------------ #
# Fixtures (module-scoped to share state + event loop)                #
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(scope="module")
async def svc():
    """Create OntologyService (module-scoped)."""
    entity_repo = FirestoreEntityRepository()
    relationship_repo = FirestoreRelationshipRepository()
    document_repo = FirestoreDocumentRepository()
    protocol_repo = FirestoreProtocolRepository()
    blindspot_repo = FirestoreBlindspotRepository()
    return OntologyService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        document_repo=document_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )


@pytest_asyncio.fixture(scope="module")
async def gov():
    """Create GovernanceService (module-scoped)."""
    entity_repo = FirestoreEntityRepository()
    relationship_repo = FirestoreRelationshipRepository()
    document_repo = FirestoreDocumentRepository()
    protocol_repo = FirestoreProtocolRepository()
    blindspot_repo = FirestoreBlindspotRepository()
    return GovernanceService(
        entity_repo=entity_repo,
        document_repo=document_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )


# Mutable state shared across ordered tests
_ids: dict[str, str] = {}
_doc_ids: list[str] = []
_blindspot_ids: list[str] = []


async def _upsert_entity_idempotent(svc: OntologyService, data: dict) -> str:
    """Upsert entity and tolerate reruns against non-empty Firestore."""
    try:
        result = await svc.upsert_entity(data)
        assert result.entity.id is not None
        return result.entity.id
    except ValueError as exc:
        msg = str(exc)
        if "already exists" not in msg:
            raise

        # Prefer explicit id from validation error:
        # "... already exists (id=xxx)."
        match = re.search(r"id=([^)]+)\)", msg)
        if match:
            return match.group(1)

        # Fallback by name lookup when message format changes.
        existing = await svc.get_entity(data["name"])
        if existing and existing.entity.id:
            return existing.entity.id
        raise


# ================================================================== #
# Step 1 -- Build the Paceriz ontology                                #
# ================================================================== #

async def test_step1_01_upsert_paceriz(svc):
    entity_id = await _upsert_entity_idempotent(svc, {
        "name": "Paceriz",
        "type": "product",
        "summary": (
            "AI 驅動的個人化跑步訓練助手，"
            "整合多平台運動數據，用科學化訓練負荷管理幫跑者安全進步"
        ),
        "tags": {
            "what": "AI 跑步教練 App",
            "why": "讓每個跑者都有一位專業的 AI 教練",
            "how": "整合 Garmin/Apple Health 數據 + ACWR + AI 建議",
            "who": "休閒到競技跑者（5K ~ 馬拉松）",
        },
        "status": "active",
    })
    _ids["paceriz"] = entity_id


async def test_step1_02_upsert_rizo_ai(svc):
    entity_id = await _upsert_entity_idempotent(svc, {
        "name": "Rizo AI",
        "type": "module",
        "summary": "基於統一數據模型，提供個性化訓練建議的 AI 教練",
        "tags": {
            "what": "AI 教練模組",
            "why": "核心差異化 — 個人化 AI 訓練建議",
            "how": "基於運動數據 + 訓練計畫，用 LLM 分析表現並給建議",
            "who": "跑者（終端用戶）",
        },
        "status": "active",
        "parent_id": _ids["paceriz"],
        "force": True,
        "manual_override_reason": "E2E 測試：先建 module，impacts 後補",
    })
    _ids["rizo_ai"] = entity_id


async def test_step1_03_upsert_training_plan(svc):
    entity_id = await _upsert_entity_idempotent(svc, {
        "name": "訓練計畫系統",
        "type": "module",
        "summary": "自動產生週課表、週回顧、提前生成下週課表",
        "tags": {
            "what": "訓練計畫模組",
            "why": "讓跑者每週有結構化的訓練計畫",
            "how": "根據 ACWR 安全機制 + 用戶目標自動排課",
            "who": "跑者（終端用戶）",
        },
        "status": "active",
        "parent_id": _ids["paceriz"],
        "force": True,
        "manual_override_reason": "E2E 測試：先建 module，impacts 後補",
    })
    _ids["training_plan"] = entity_id


async def test_step1_04_upsert_data_integration(svc):
    entity_id = await _upsert_entity_idempotent(svc, {
        "name": "運動數據整合",
        "type": "module",
        "summary": "Garmin/Apple Health/Strava 多平台運動數據統一模型",
        "tags": {
            "what": "運動數據整合模組",
            "why": "統一不同手錶/平台的數據格式",
            "how": "Adapter 架構 + UnifiedWorkoutModel",
            "who": "後端開發者",
        },
        "status": "active",
        "parent_id": _ids["paceriz"],
        "force": True,
        "manual_override_reason": "E2E 測試：先建 module，impacts 後補",
    })
    _ids["data_integration"] = entity_id


async def test_step1_05_upsert_acwr(svc):
    entity_id = await _upsert_entity_idempotent(svc, {
        "name": "ACWR 安全機制",
        "type": "module",
        "summary": "急慢性訓練負荷比，防止過度訓練",
        "tags": {
            "what": "ACWR 安全機制模組",
            "why": "防止跑者因過度訓練受傷",
            "how": "計算 Acute:Chronic Workload Ratio，設定安全閾值",
            "who": "跑者（間接受益）、後端開發者",
        },
        "status": "active",
        "parent_id": _ids["paceriz"],
        "force": True,
        "manual_override_reason": "E2E 測試：先建 module，impacts 後補",
        "details": {
            "known_issues": [
                "第一週無保護（ACWR = 9999）",
                "Taper 後恢復缺失",
                "邏輯一致性衝突",
            ],
        },
    })
    _ids["acwr"] = entity_id


async def test_step1_06_add_relationships(svc):
    rels = [
        (_ids["rizo_ai"], _ids["data_integration"], "depends_on",
         "Rizo AI 需要統一數據模型來分析跑步表現"),
        (_ids["rizo_ai"], _ids["training_plan"], "depends_on",
         "Rizo AI 需要訓練計畫來給出個人化建議"),
        (_ids["training_plan"], _ids["acwr"], "depends_on",
         "訓練計畫需要 ACWR 保護跑者安全"),
        (_ids["acwr"], _ids["data_integration"], "depends_on",
         "ACWR 計算需要歷史運動數據"),
        (_ids["rizo_ai"], _ids["paceriz"], "part_of",
         "Rizo AI 是 Paceriz 的核心模組"),
    ]
    for src, tgt, rtype, desc in rels:
        r = await svc.add_relationship(
            source_id=src, target_id=tgt, rel_type=rtype, description=desc,
        )
        assert r.id is not None


async def test_step1_07_upsert_documents(svc):
    base = "https://github.com/havital/cloud/blob/main"
    docs = [
        {
            "title": "API 開發規範 (CLAUDE.md)",
            "source": {"type": "github", "uri": f"{base}/cloud/api_service/CLAUDE.md", "adapter": "github"},
            "tags": {"what": ["API 開發規範", "架構規則"], "why": "開發效率 + 安全", "how": "架構規則、測試規範", "who": ["開發者（AI）"]},
            "summary": "API 服務的開發規範和架構規則",
            "linked_entity_ids": [_ids["paceriz"]],
        },
        {
            "title": "Firestore 完整結構",
            "source": {"type": "github", "uri": f"{base}/cloud/api_service/FIRESTORE_STRUCTURE.md", "adapter": "github"},
            "tags": {"what": ["Firestore 結構", "資料模型"], "why": "資料模型 SSOT", "how": "所有 Collection 定義", "who": ["後端開發"]},
            "summary": "Firestore 資料庫完整結構定義",
            "linked_entity_ids": [_ids["data_integration"], _ids["training_plan"]],
        },
        {
            "title": "ACWR 專家回饋分析",
            "source": {"type": "github", "uri": f"{base}/cloud/api_service/EXPERT_FEEDBACK_ANALYSIS.md", "adapter": "github"},
            "tags": {"what": ["ACWR 專家回饋", "安全問題分析"], "why": "安全改善", "how": "專家回饋 + 問題確認", "who": ["開發者", "產品"]},
            "summary": "ACWR 三項已確認的安全問題及專家分析",
            "linked_entity_ids": [_ids["acwr"]],
        },
        {
            "title": "官網產品描述",
            "source": {"type": "github", "uri": f"{base}/web/official_web/README.md", "adapter": "github"},
            "tags": {"what": ["官網", "產品描述"], "why": "對外展示", "how": "網站結構 + 設計", "who": ["行銷", "用戶"]},
            "summary": "Paceriz 官網設計理念、產品描述和結構",
            "linked_entity_ids": [_ids["paceriz"]],
        },
    ]
    for d in docs:
        result = await svc.upsert_document(d)
        assert result.id is not None
        assert result.sources
        assert result.sources[0]["uri"].startswith("https://github.com/")
        _doc_ids.append(result.id)

    _ids["acwr_doc"] = _doc_ids[2]


async def test_step1_08_add_blindspots(svc):
    items = [
        {
            "description": "marketing/ 裡沒有行銷素材，全是技術文件。",
            "severity": "red",
            "suggested_action": "用 Context Protocol 作為行銷夥伴的入口。",
            "related_entity_ids": [_ids["paceriz"]],
        },
        {
            "description": "ACWR 三項安全問題已確認但未排修復時程。",
            "severity": "red",
            "suggested_action": "明確定義修復優先順序。安全 > 功能。",
            "related_entity_ids": [_ids["acwr"]],
        },
        {
            "description": "一次性開發報告混在活文件中。",
            "severity": "yellow",
            "suggested_action": "把一次性報告移到 archive/。",
            "related_entity_ids": [_ids["paceriz"]],
        },
        {
            "description": "Notebook POC 是寶貴知識但完全沒索引。",
            "severity": "yellow",
            "suggested_action": "為每個 notebook 建立索引表。",
            "related_entity_ids": [_ids["rizo_ai"], _ids["training_plan"]],
        },
    ]
    for data in items:
        result = await svc.add_blindspot(data)
        assert result.id is not None
        assert result.severity in ("red", "yellow", "green")
        _blindspot_ids.append(result.id)


async def test_step1_09_upsert_protocol(svc):
    result = await svc.upsert_protocol({
        "entity_id": _ids["paceriz"],
        "entity_name": "Paceriz",
        "content": {
            "what": {
                "product_name": "Paceriz",
                "slogan": "你的個人化跑步訓練助手",
                "category": "運動科技 / AI 教練",
                "company": "Naruvia",
                "summary": "AI 跑步教練 App",
                "core_features": [
                    "多平台數據整合",
                    "AI 週訓練計畫",
                    "AI 教練 Rizo",
                    "科學化指標",
                    "週回顧 + 下週預排",
                ],
            },
            "why": {
                "current_goal": "v2 課表流程驗證 + Agent 導入",
                "vision": "讓每個跑者都有專業 AI 教練",
            },
            "how": {
                "in_progress": ["v2 課表流程", "Agent 導入", "官網更新"],
                "completed": ["Garmin 同步", "Apple Health", "VDOT/TSS"],
            },
            "who": {
                "internal": {"dev": "Barry", "marketing": "行銷夥伴"},
                "target_users": "休閒到競技跑者",
                "market": "台灣優先",
            },
        },
        "gaps": [
            {"description": "商業動機不明", "priority": "red"},
            {"description": "成功指標不明", "priority": "red"},
            {"description": "時程不明", "priority": "red"},
            {"description": "用戶規模不明", "priority": "yellow"},
            {"description": "競品定位缺失", "priority": "yellow"},
        ],
        "version": "0.2",
    })
    assert result.id is not None
    assert result.entity_name == "Paceriz"
    assert result.entity_id == _ids["paceriz"]
    _ids["protocol"] = result.id


# ================================================================== #
# Step 2 -- Consumer-side verification                                #
# ================================================================== #

async def test_step2_01_get_protocol(svc):
    protocol = await svc.get_protocol("Paceriz")
    assert protocol is not None
    assert protocol.entity_name == "Paceriz"
    assert "what" in protocol.content
    assert "why" in protocol.content
    assert "how" in protocol.content
    assert "who" in protocol.content
    assert protocol.content["what"]["product_name"] == "Paceriz"
    assert len(protocol.gaps) >= 3


async def test_step2_02_list_entities_modules(svc):
    modules = await svc.list_entities(type_filter="module")
    assert len(modules) >= 4
    names = {e.name for e in modules}
    assert ("Rizo AI" in names) or ("Rizo AI 教練" in names)
    assert "訓練計畫系統" in names
    assert "運動數據整合" in names
    assert "ACWR 安全機制" in names


async def test_step2_03_get_entity_rizo(svc):
    result = await svc.get_entity("Rizo AI")
    if result is None:
        result = await svc.get_entity("Rizo AI 教練")
    assert result is not None
    assert "Rizo AI" in result.entity.name
    assert result.entity.type == "module"
    assert len(result.relationships) >= 2
    rel_types = {r.type for r in result.relationships}
    assert "depends_on" in rel_types


async def test_step2_04_list_blindspots_red(svc):
    blindspots = await svc.list_blindspots(severity="red")
    assert len(blindspots) >= 2
    for bs in blindspots:
        assert bs.severity == "red"


async def test_step2_05_search_acwr(svc):
    results = await svc.search("ACWR")
    assert len(results) >= 1


async def test_step2_06_get_document(svc):
    doc = await svc.get_document(_ids["acwr_doc"])
    assert doc is not None
    doc_name = getattr(doc, "title", None) or getattr(doc, "name", "")
    assert doc_name == "ACWR 專家回饋分析"
    if hasattr(doc, "source"):
        assert doc.source.type == "github"
        assert doc.source.uri.startswith("https://github.com/")
    else:
        assert doc.sources
        assert doc.sources[0]["type"] == "github"
        assert doc.sources[0]["uri"].startswith("https://github.com/")


async def test_step2_07_no_local_paths(svc):
    for doc_id in _doc_ids:
        doc = await svc.get_document(doc_id)
        assert doc is not None
        if hasattr(doc, "source"):
            uri = doc.source.uri
        else:
            uri = doc.sources[0]["uri"] if doc.sources else ""
        doc_name = getattr(doc, "title", None) or getattr(doc, "name", "")
        assert uri.startswith("https://"), (
            f"Document '{doc_name}' has non-HTTPS URI: {uri}"
        )


# ================================================================== #
# Step 3 -- Governance-side verification                              #
# ================================================================== #

async def test_step3_01_list_unconfirmed(svc):
    result = await svc.list_unconfirmed()
    total = sum(len(items) for items in result.values())
    assert total >= 1, "Should have at least some unconfirmed items"


async def test_step3_02_confirm_entity(svc):
    result = await svc.confirm("entities", _ids["paceriz"])
    assert result["confirmed_by_user"] is True
    assert result["collection"] == "entities"

    # Verify by fetching the specific entity by ID (not by name, since
    # previous test runs may have left older entries with the same name).
    from zenos.infrastructure.firestore_repo import FirestoreEntityRepository
    repo = FirestoreEntityRepository()
    confirmed_entity = await repo.get_by_id(_ids["paceriz"])
    assert confirmed_entity is not None
    assert confirmed_entity.confirmed_by_user is True


async def test_step3_03_quality_check(gov):
    report = await gov.run_quality_check()
    assert 0 <= report.score <= 100
    total = len(report.passed) + len(report.failed) + len(report.warnings)
    assert total >= 1


async def test_step3_04_staleness_check(gov):
    warnings = await gov.run_staleness_check()
    assert isinstance(warnings, dict)
    assert "warnings" in warnings


async def test_step3_05_blindspot_analysis(gov):
    blindspots = await gov.run_blindspot_analysis()
    assert isinstance(blindspots, list)
