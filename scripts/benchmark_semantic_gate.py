"""Benchmark: Can Gemini Flash 2.5 Lite handle semantic governance?

Tests 3 governance capabilities with real Paceriz examples:
  1. L2 三問驗證 — is this a valid L2 concept?
  2. Summary 語言品質 — is the summary written in consensus language?
  3. Impacts 品質判斷 — is the impact relationship specific enough?

Each test case has a known expected answer. We run each N times
to measure stability (same input → same answer?).

Usage:
    cd src && python -m scripts.benchmark_semantic_gate
    # or directly:
    PYTHONPATH=src python scripts/benchmark_semantic_gate.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

# Add src to path so we can import zenos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from zenos.infrastructure.llm_client import create_llm_client


# ──────────────────────────────────────────────
# Response Schemas
# ──────────────────────────────────────────────

class L2ThreeQuestionResult(BaseModel):
    is_consensus: bool
    consensus_reason: str
    has_downstream_impact: bool
    impact_reason: str
    survives_over_time: bool
    time_reason: str
    verdict: str  # "pass" | "fail"


class SummaryLanguageResult(BaseModel):
    is_consensus_language: bool
    has_tech_jargon: bool
    has_marketing_fluff: bool
    anyone_understands: bool
    verdict: str  # "pass" | "fail"
    issues: list[str]
    rewrite_suggestion: str


class ImpactQualityResult(BaseModel):
    has_concrete_scenario: bool
    specifies_what_changes: bool
    specifies_what_to_check: bool
    verdict: str  # "pass" | "fail"
    reason: str


class IncrementalRoutingResult(BaseModel):
    action: str  # "update_existing" | "create_new" | "ignore"
    target_entity_id: str  # existing entity ID if update, "" if create_new or ignore
    reason: str
    suggested_changes: str  # what to update or what the new entity should be


# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────

L2_THREE_QUESTION_SYSTEM = """你是 ontology 品質審計員。判斷一個概念是否值得成為 L2 entity。

L2 entity 的本質：公司知識圖譜中的節點。它存在的理由不是「記錄資訊」，
是「當它改變時，能透過關聯告訴你還有誰要跟著動」。

依序回答三個問題：

1. **共識性** — 這個概念是否跨角色成立？
   判斷原則：知識是否被角色邊界鎖住。
   如果只有某個專業角色才能理解這件事的真偽，它就不是共識。
   如果任何角色聽到一句話解釋後都會同意「對，這是事實」，它就是共識。
   注意：共識不要求所有人事先知道這個名詞，而是理解後都認同。

2. **影響性** — 這個概念改變時，是否存在其他概念必須跟著重新檢視？
   判斷原則：概念之間是否存在耦合。
   如果改了它，知識圖譜中沒有任何其他節點需要更新，它就沒有影響性。
   影響的對象必須是其他概念，不是具體的程式碼或 UI 元素。

3. **持續性** — 這個概念描述的是一個狀態還是一個事件？
   判斷原則：它描述的是「事情是怎樣的」還是「發生了什麼事」。
   狀態會持續為真直到被更新。事件發生完就結束了。
   注意：有明確終止條件的狀態（如「目前在 Phase 0」）仍然是狀態，
   只要它在終止前持續影響決策。

三個都通過 = verdict "pass"，任何一個不通過 = verdict "fail"。

回傳嚴格符合以下格式的 flat JSON（不要巢狀）：
{
  "is_consensus": true,
  "consensus_reason": "...",
  "has_downstream_impact": true,
  "impact_reason": "...",
  "survives_over_time": true,
  "time_reason": "...",
  "verdict": "pass"
}"""


SUMMARY_LANGUAGE_SYSTEM = """你是 ontology 語言品質審計員。判斷 L2 entity 的 summary 是否用「共識語言」寫成。

共識語言的標準：
- 公司裡任何角色（行銷、客服、工程師、老闆）讀了都能理解
- 不依賴專業背景知識
- 不是技術語言（不該出現：API、schema、LLM、framework、middleware、endpoint、SDK、pipeline、deployment、data model、prompt）
- 不是行銷語言（不該出現：顛覆性、業界領先、獨家、全球首創、革命性）
- 是事實陳述，不是推銷

回傳**嚴格符合以下格式的 flat JSON**（不要巢狀，不要包在其他物件裡）：
{
  "is_consensus_language": true,
  "has_tech_jargon": false,
  "has_marketing_fluff": false,
  "anyone_understands": true,
  "verdict": "pass",
  "issues": [],
  "rewrite_suggestion": ""
}
如果 verdict 是 "fail"，在 issues 列出問題，在 rewrite_suggestion 提供改寫建議。"""


INCREMENTAL_ROUTING_SYSTEM = """你是 ontology 治理引擎。你的任務是判斷一段新資訊應該如何處理。

你會收到：
- 一段新資訊（可能來自 git commit、對話、或文件變更）
- 現有的 L2 概念清單（每個有 id、name、summary）

你要判斷這段新資訊：

1. **update_existing** — 它描述的是某個既有 L2 概念的變化或更新。
   判斷原則：新資訊的語意核心與某個既有 L2 重疊。
   不是名稱相似就算重疊，而是它們描述的是同一個公司共識。

2. **create_new** — 它描述的是一個全新的公司共識概念，現有 L2 都不涵蓋。
   判斷原則：這段資訊通過 L2 三問（跨角色共識 + 有下游影響 + 持續為真），
   且無法歸入任何既有 L2 的範圍。

3. **ignore** — 它不值得進入 L2 層。
   判斷原則：它是技術細節、一次性事件、或某個角色的專屬知識。

回傳嚴格符合以下格式的 flat JSON（不要巢狀）：
{
  "action": "update_existing",
  "target_entity_id": "entity-id-here",
  "reason": "...",
  "suggested_changes": "..."
}
target_entity_id 在 action 為 create_new 或 ignore 時填空字串 ""。"""


IMPACT_QUALITY_SYSTEM = """你是 ontology 關係品質審計員。判斷一條 impacts 關係是否有價值。

一條有價值的 impacts 關係必須能回答：
「A 改了什麼的時候，B 的什麼地方要跟著看？」

品質標準：
- has_concrete_scenario: 能具體說出改變場景（不是抽象的「A 依賴 B」）
- specifies_what_changes: 有說明 A 的什麼會改
- specifies_what_to_check: 有說明 B 的什麼要跟著看

三個都通過 = "pass"，任何一個不通過 = "fail"。

回傳**嚴格符合以下格式的 flat JSON**（不要巢狀，不要包在其他物件裡）：
{
  "has_concrete_scenario": true,
  "specifies_what_changes": true,
  "specifies_what_to_check": true,
  "verdict": "pass",
  "reason": "..."
}"""


# ──────────────────────────────────────────────
# Test Cases
# ──────────────────────────────────────────────

@dataclass
class TestCase:
    name: str
    capability: str  # "l2_three_questions" | "summary_language" | "impact_quality"
    input_data: dict[str, Any]
    expected_verdict: str  # "pass" | "fail"
    reason: str  # why we expect this verdict


# --- Capability 1: L2 三問驗證 ---

L2_TEST_CASES = [
    # === Should PASS ===
    TestCase(
        name="安全機制（good L2）",
        capability="l2_three_questions",
        input_data={
            "name": "安全機制",
            "summary": "AI 不會讓你練到受傷。系統追蹤你的訓練負荷，如果偵測到訓練量暴增，自動降量保護你。",
            "tags": {
                "what": "Paceriz、訓練安全",
                "why": "跑者最怕練到受傷，這是用戶信任的基礎",
                "who": "跑者、客服、行銷、後端工程師",
                "how": "每次跑完計算近期 vs 長期訓練負荷比，超過安全值就降量",
            },
        },
        expected_verdict="pass",
        reason="符合三問：所有人都同意、改了影響客服話術/App提示、持續為真",
    ),
    TestCase(
        name="收費模型（good L2）",
        capability="l2_three_questions",
        input_data={
            "name": "收費模型",
            "summary": "按公司收費，不按人頭。三段式計費：月費基底 + LLM 使用量 + 雲端儲存。",
            "tags": {
                "what": "ZenOS、定價",
                "why": "SMB 預算有限，按公司收費降低決策門檻",
                "who": "老闆、行銷、客服、財務",
                "how": "一個公司一個帳號，月費固定，超量另計",
            },
        },
        expected_verdict="pass",
        reason="符合三問：所有人都同意定價方式、改了影響行銷/合約/onboarding、持續為真",
    ),
    TestCase(
        name="V2 訓練流程（good L2）",
        capability="l2_three_questions",
        input_data={
            "name": "訓練流程 V2",
            "summary": "AI 每週幫跑者生成個人化課表。跑完之後自動回顧這週訓練，根據回顧調整下週計畫。三步循環：計畫 → 執行 → 回顧 → 下週計畫。",
            "tags": {
                "what": "Paceriz、核心功能",
                "why": "這是產品的核心價值主張",
                "who": "跑者、行銷、客服、工程師",
                "how": "AI 根據用戶目標和歷史數據，每週自動生成和調整訓練計畫",
            },
        },
        expected_verdict="pass",
        reason="符合三問：核心功能所有人都知道、改循環影響所有角色、持續為真",
    ),
    # === Should FAIL ===
    TestCase(
        name="MCP Server framework（技術細節，非共識）",
        capability="l2_three_questions",
        input_data={
            "name": "MCP Server 技術選型",
            "summary": "MCP Server 使用 FastMCP framework，基於 Python asyncio，支援 SSE transport。",
            "tags": {
                "what": "ZenOS、MCP",
                "why": "提供穩定的 AI agent 接入介面",
                "who": "後端工程師",
                "how": "FastMCP + SSE + Cloud Run 部署",
            },
        },
        expected_verdict="fail",
        reason="只有工程師知道 FastMCP 是什麼，行銷/客服不會點頭",
    ),
    TestCase(
        name="今天部署了 hotfix（一次性事件）",
        capability="l2_three_questions",
        input_data={
            "name": "2026-03-24 Hotfix 部署",
            "summary": "修復了 Dashboard 知識地圖頁面 L2 節點展開失敗的 bug，原因是 task fallback 邏輯缺失。",
            "tags": {
                "what": "Dashboard、知識地圖",
                "why": "用戶無法展開 L2 節點查看詳細資訊",
                "who": "前端工程師",
                "how": "補上 task fallback 邏輯 + re-expand 穩定性修復",
            },
        },
        expected_verdict="fail",
        reason="一次性事件，不跨時間存活，應該在 git log 裡",
    ),
    TestCase(
        name="Dashboard 按鈕顏色（無下游影響）",
        capability="l2_three_questions",
        input_data={
            "name": "Dashboard 主按鈕樣式",
            "summary": "Dashboard 的主要操作按鈕使用藍色（#3B82F6），hover 時加深。",
            "tags": {
                "what": "Dashboard、UI",
                "why": "視覺一致性",
                "who": "前端工程師、設計師",
                "how": "Tailwind CSS class: bg-blue-500 hover:bg-blue-600",
            },
        },
        expected_verdict="fail",
        reason="改了按鈕顏色不會影響其他概念，沒有下游 impact",
    ),
    TestCase(
        name="Firestore billing schema（只有工程師懂）",
        capability="l2_three_questions",
        input_data={
            "name": "Firestore Billing Collection Schema",
            "summary": "billing/{partnerId}/invoices subcollection 存放月帳單，每筆含 base_fee、llm_usage、storage_usage 欄位。",
            "tags": {
                "what": "ZenOS、計費、Firestore",
                "why": "結構化儲存帳單資料",
                "who": "後端工程師",
                "how": "Firestore subcollection + Cloud Functions 月結觸發",
            },
        },
        expected_verdict="fail",
        reason="技術 schema 細節，只有工程師懂，是 L3 不是 L2",
    ),
    # === Edge Cases ===
    TestCase(
        name="Phase 0 開發階段（有終止條件的狀態）",
        capability="l2_three_questions",
        input_data={
            "name": "Phase 0 概念驗證",
            "summary": "ZenOS 目前處於 Phase 0 概念驗證階段，第一個客戶是 Paceriz（自家 dogfooding）。目標是驗證 ontology + MCP 的核心價值主張。",
            "tags": {
                "what": "ZenOS、專案階段",
                "why": "確定方向對了再投入更多資源",
                "who": "所有人",
                "how": "用 Paceriz 做 dogfooding，驗證 AI agent 能否從 ontology 獲取足夠 context",
            },
        },
        expected_verdict="pass",
        reason="所有人都知道在 Phase 0、改了影響整個團隊方向、是持續狀態直到進 Phase 1",
    ),
    # === 更多 should PASS ===
    TestCase(
        name="客戶上手流程（跨角色共識）",
        capability="l2_three_questions",
        input_data={
            "name": "客戶上手流程",
            "summary": "新客戶從註冊到第一次使用 AI agent 的完整流程：開帳號、設定 API key、在自己的工具裡貼上連線設定、AI agent 自動讀取公司知識。",
            "tags": {
                "what": "ZenOS、客戶體驗",
                "why": "上手流程的順暢度直接影響客戶是否留下來",
                "who": "客戶、客服、行銷、產品",
                "how": "Dashboard 自助設定 + 一鍵複製 MCP 連線設定",
            },
        },
        expected_verdict="pass",
        reason="跨角色都理解、改了影響行銷話術/客服支援/Dashboard UI、持續為真",
    ),
    TestCase(
        name="漸進式信任機制（產品核心原則）",
        capability="l2_three_questions",
        input_data={
            "name": "漸進式信任",
            "summary": "AI agent 剛接上時只能讀取基本資訊，隨著使用者確認更多知識，AI 能做的事逐步增加。不是一開始就全部開放。",
            "tags": {
                "what": "ZenOS、信任模型",
                "why": "降低客戶對 AI 存取公司資料的疑慮",
                "who": "客戶、產品、工程師、行銷",
                "how": "confirmed_by_user 標記 + 權限層級",
            },
        },
        expected_verdict="pass",
        reason="跨角色都理解信任問題、改了影響產品定位/行銷/權限設計、持續為真",
    ),
    TestCase(
        name="品質保證（產品功能共識）",
        capability="l2_three_questions",
        input_data={
            "name": "品質保證",
            "summary": "每份課表送出前都經過 4 層 AI 審計：計畫結構合理嗎、訓練量安全嗎、回顧數據正確嗎、回饋有被採納嗎。",
            "tags": {
                "what": "Paceriz、品質",
                "why": "用戶信任的基礎——確保 AI 生成的課表不會出錯",
                "who": "跑者、行銷、客服、工程師",
                "how": "課表生成後經過 4 層自動審計才送出",
            },
        },
        expected_verdict="pass",
        reason="所有人都同意品質很重要、改了影響行銷話術/客服說法/上線標準、持續為真",
    ),
    # === 更多 should FAIL ===
    TestCase(
        name="Sprint 14 排程（PM 專屬知識）",
        capability="l2_three_questions",
        input_data={
            "name": "Sprint 14 排程",
            "summary": "Sprint 14 預計完成 Dashboard v2 重構、Task isolation、User invitation 三個 feature。3/25 開始，4/5 結束。",
            "tags": {
                "what": "ZenOS、專案管理",
                "why": "確保開發進度可控",
                "who": "PM、工程師",
                "how": "兩週一個 sprint，Kanban 追蹤",
            },
        },
        expected_verdict="fail",
        reason="Sprint 排程是 PM 專屬知識，行銷/客服不需要知道；改了不影響其他概念",
    ),
    TestCase(
        name="Firestore index 設定（基礎設施細節）",
        capability="l2_three_questions",
        input_data={
            "name": "Firestore Composite Index",
            "summary": "entities collection 需要 (partner_id, type, status) composite index 來支援 Dashboard 查詢效能。",
            "tags": {
                "what": "ZenOS、Firestore",
                "why": "查詢效能",
                "who": "後端工程師",
                "how": "firebase.json 定義 composite index",
            },
        },
        expected_verdict="fail",
        reason="只有工程師懂什麼是 composite index，純基礎設施細節",
    ),
    TestCase(
        name="上週五的 demo（一次性事件）",
        capability="l2_three_questions",
        input_data={
            "name": "2026-03-21 投資人 Demo",
            "summary": "上週五向 Seed 輪投資人展示了 ZenOS 的知識地圖 + MCP 連線 demo，反應正面，預計下週安排第二次會面。",
            "tags": {
                "what": "ZenOS、募資",
                "why": "爭取 Seed 輪資金",
                "who": "老闆、投資人",
                "how": "線上 demo + 現場 Q&A",
            },
        },
        expected_verdict="fail",
        reason="一次性事件，發生完就結束了，不是持續為真的狀態",
    ),
    TestCase(
        name="Git branching strategy（工程實務）",
        capability="l2_three_questions",
        input_data={
            "name": "Git 分支策略",
            "summary": "main branch 為 production，feature branch 從 main 開出，PR review 後 squash merge 回 main。",
            "tags": {
                "what": "ZenOS、開發流程",
                "why": "維持程式碼品質和可追蹤性",
                "who": "工程師",
                "how": "GitHub PR + squash merge",
            },
        },
        expected_verdict="fail",
        reason="只有工程師需要知道 Git 分支策略，被角色邊界鎖住",
    ),
]

# --- Capability 4: Incremental Routing ---

# Simulated existing L2 entities (Paceriz ontology)
EXISTING_L2_ENTITIES = [
    {"id": "l2-001", "name": "訓練流程 V2", "summary": "AI 每週幫跑者生成個人化課表。跑完之後自動回顧這週訓練，根據回顧調整下週計畫。三步循環：計畫 → 執行 → 回顧 → 下週計畫。"},
    {"id": "l2-002", "name": "安全機制", "summary": "AI 不會讓你練到受傷。系統追蹤你的訓練負荷，如果偵測到訓練量暴增，自動降量保護你。"},
    {"id": "l2-003", "name": "品質保證", "summary": "每份課表送出前都經過 4 層 AI 審計：計畫結構合理嗎、訓練量安全嗎、回顧數據正確嗎、回饋有被採納嗎。"},
    {"id": "l2-004", "name": "V2 上線狀態", "summary": "TestFlight 測試中。有兩個 P0 bug 待修。Launch gate 尚未通過。"},
    {"id": "l2-005", "name": "收費模型", "summary": "按公司收費，不按人頭。三段式計費：月費基底 + AI 使用量 + 雲端儲存。"},
    {"id": "l2-006", "name": "客戶上手流程", "summary": "新客戶從註冊到第一次使用 AI agent 的完整流程：開帳號、設定 API key、在自己的工具裡貼上連線設定、AI agent 自動讀取公司知識。"},
    {"id": "l2-007", "name": "漸進式信任", "summary": "AI agent 剛接上時只能讀取基本資訊，隨著使用者確認更多知識，AI 能做的事逐步增加。不是一開始就全部開放。"},
]

INCREMENTAL_ROUTING_TEST_CASES = [
    # === update_existing: 新資訊屬於既有 L2 ===
    TestCase(
        name="安全閾值調整→更新安全機制",
        capability="incremental_routing",
        input_data={
            "new_info": "團隊決定把 ACWR 安全閾值從 1.3 調高到 1.5，讓進階跑者有更大的訓練彈性。同時調低新手的閾值到 1.1。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="安全閾值是「安全機制」L2 的核心內容，應該更新 l2-002",
    ),
    TestCase(
        name="V2 bug 修完→更新上線狀態",
        capability="incremental_routing",
        input_data={
            "new_info": "兩個 P0 bug 都修完了：課表顯示問題和 workout 分析超時。QA 已通過，準備提交 App Store Review。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="直接更新 V2 上線狀態（l2-004），bug 狀態變了",
    ),
    TestCase(
        name="品質審計加第 5 層→更新品質保證",
        capability="incremental_routing",
        input_data={
            "new_info": "新增第 5 層品質審計：檢查課表是否符合用戶的時間偏好（例如：用戶說只能早上跑，課表不能排下午）。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="品質審計層數變了，應該更新「品質保證」l2-003",
    ),
    TestCase(
        name="收費改成純月費→更新收費模型",
        capability="incremental_routing",
        input_data={
            "new_info": "老闆決定簡化定價：取消三段式，改成單一月費制。LLM 和儲存成本由公司吸收。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="定價策略根本改變，更新「收費模型」l2-005",
    ),
    TestCase(
        name="週回顧改成即時回饋→更新訓練流程",
        capability="incremental_routing",
        input_data={
            "new_info": "訓練流程重大改版：取消每週一次的集中回顧，改成每次跑完即時回饋。循環從三步變兩步：計畫 → 執行（含即時回饋）→ 下週計畫。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="訓練流程核心循環改了，更新 l2-001",
    ),
    # === create_new: 全新的 L2 概念 ===
    TestCase(
        name="社群功能（全新概念）",
        capability="incremental_routing",
        input_data={
            "new_info": "產品決定加入社群功能：跑者可以組成跑團，分享訓練計畫，互相鼓勵。團長可以看到團員的訓練狀況。這是下一季的重點方向。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="create_new",
        reason="社群功能是全新方向，現有 L2 沒有涵蓋，且符合三問",
    ),
    TestCase(
        name="多語系支援（全新概念）",
        capability="incremental_routing",
        input_data={
            "new_info": "為了進軍日本市場，產品將支援日文介面和日文課表生成。這影響所有面向用戶的文字、客服流程、行銷素材。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="create_new",
        reason="多語系是全新的跨角色共識，改了影響所有面向用戶的東西，不屬於任何既有 L2",
    ),
    TestCase(
        name="競品定位（全新概念）",
        capability="incremental_routing",
        input_data={
            "new_info": "分析完競品後確認：Paceriz 的差異化在「AI 個人化 + 安全機制」，其他跑步 App（Nike Run Club、Strava）都沒有 AI 課表生成 + 安全閥。這是行銷和產品的核心定位。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="create_new",
        reason="競品定位是獨立的公司共識，不屬於任何既有功能描述的 L2",
    ),
    # === ignore: 不該進 L2 ===
    TestCase(
        name="修了一個 CSS bug（一次性事件）",
        capability="incremental_routing",
        input_data={
            "new_info": "commit: fix(dashboard): 修正知識地圖頁面在 Safari 上節點重疊的 CSS 問題",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="ignore",
        reason="一次性 bug fix，不是公司共識概念",
    ),
    TestCase(
        name="重構了 Firestore query（技術細節）",
        capability="incremental_routing",
        input_data={
            "new_info": "commit: refactor(infra): 把 Firestore 查詢從 list_all + filter 改成 compound query，減少讀取量 80%",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="ignore",
        reason="純技術重構，只有工程師需要知道",
    ),
    TestCase(
        name="更新了依賴版本（維運細節）",
        capability="incremental_routing",
        input_data={
            "new_info": "commit: chore(deps): 升級 litellm 從 1.74 到 1.82，Next.js 從 15.1 到 15.2",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="ignore",
        reason="依賴升級，純維運，不影響任何公司共識概念",
    ),
    TestCase(
        name="寫了一份內部 API 文件（L3 不是 L2）",
        capability="incremental_routing",
        input_data={
            "new_info": "新增 docs/api/mcp-tools-reference.md，記錄所有 MCP tool 的參數格式和回傳值，給工程師整合時查閱。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="ignore",
        reason="工程師專用的 API 文件，是 L3 不是 L2",
    ),
    # === 邊界案例 ===
    TestCase(
        name="onboarding 流程大改版（更新 vs 新建的邊界）",
        capability="incremental_routing",
        input_data={
            "new_info": "客戶上手流程完全重新設計：取消手動設定 API key 的步驟，改成掃 QR code 一鍵連線。整個流程從 5 步縮短到 2 步。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="雖然大改但還是「客戶上手流程」這個概念，應該更新 l2-006 不是新建",
    ),
    TestCase(
        name="信任機制加入企業管控（擴展既有概念）",
        capability="incremental_routing",
        input_data={
            "new_info": "漸進式信任擴展：企業客戶的管理員可以設定信任層級上限，限制 AI agent 最多能存取到哪一層資料。員工不能自行提升。",
            "existing_entities": EXISTING_L2_ENTITIES,
        },
        expected_verdict="update_existing",
        reason="是漸進式信任的延伸，更新 l2-007 而不是新建",
    ),
]

# --- Capability 2: Summary 語言品質 ---

SUMMARY_LANGUAGE_TEST_CASES = [
    # === Should PASS ===
    TestCase(
        name="安全機制 summary（共識語言）",
        capability="summary_language",
        input_data={
            "name": "安全機制",
            "summary": "AI 不會讓你練到受傷。系統追蹤你的訓練負荷，如果偵測到訓練量暴增，自動降量保護你。",
        },
        expected_verdict="pass",
        reason="任何人都看得懂，沒有技術術語，沒有行銷浮誇",
    ),
    TestCase(
        name="收費模型 summary（共識語言）",
        capability="summary_language",
        input_data={
            "name": "收費模型",
            "summary": "按公司收費，不按人頭。三段式計費：月費基底 + AI 使用量 + 雲端儲存。",
        },
        expected_verdict="pass",
        reason="簡潔事實陳述，任何人都理解",
    ),
    # === Should FAIL ===
    TestCase(
        name="技術語言 summary（工程師視角）",
        capability="summary_language",
        input_data={
            "name": "訓練計畫系統",
            "summary": "V2 三階段訓練流程：(1) Plan Overview — 雙維度設計（target_type × methodology），產生分期跑量範圍；(2) Weekly Plan — Section-based Prompt + 兩階段 LLM，輸出 V3 data model（category + typed primary）；(3) Weekly Summary — target-type 專屬 Builder",
        },
        expected_verdict="fail",
        reason="充滿技術術語：LLM、data model、Section-based Prompt，行銷/客服完全看不懂",
    ),
    TestCase(
        name="行銷浮誇語言",
        capability="summary_language",
        input_data={
            "name": "ZenOS 定位",
            "summary": "業界領先的革命性 AI Context 層，顛覆傳統知識管理，為中小企業帶來前所未有的智慧化體驗。",
        },
        expected_verdict="fail",
        reason="行銷浮誇：業界領先、革命性、顛覆、前所未有",
    ),
    TestCase(
        name="混合技術+行銷",
        capability="summary_language",
        input_data={
            "name": "MCP 整合",
            "summary": "全球首創的 MCP-native ontology engine，基於 LiteLLM middleware 提供 SSE streaming endpoint，讓每個 AI agent 都能無縫接入。",
        },
        expected_verdict="fail",
        reason="同時有技術術語（LiteLLM、middleware、SSE、endpoint）和行銷浮誇（全球首創、無縫）",
    ),
]

# --- Capability 3: Impacts 品質判斷 ---

IMPACT_QUALITY_TEST_CASES = [
    # === Should PASS ===
    TestCase(
        name="收費→onboarding（具體場景）",
        capability="impact_quality",
        input_data={
            "source": "收費模型",
            "target": "客戶上手流程",
            "description": "改定價時，onboarding 的報價說明要更新",
        },
        expected_verdict="pass",
        reason="具體說出：改定價（A的什麼）→ 報價說明要更新（B的什麼）",
    ),
    TestCase(
        name="安全閾值→客服話術（具體場景）",
        capability="impact_quality",
        input_data={
            "source": "安全機制",
            "target": "客服話術",
            "description": "安全閾值調整後，「課表變輕是因為保護機制」的觸發條件改了，客服說法要更新",
        },
        expected_verdict="pass",
        reason="具體說出觸發條件改了、客服說法要更新",
    ),
    # === Should FAIL ===
    TestCase(
        name="Dashboard depends_on Ontology（太模糊）",
        capability="impact_quality",
        input_data={
            "source": "Dashboard",
            "target": "Ontology Engine",
            "description": "Dashboard 依賴 Ontology Engine",
        },
        expected_verdict="fail",
        reason="太模糊，不知道改什麼會影響什麼",
    ),
    TestCase(
        name="auto-inferred（自動生成，無具體內容）",
        capability="impact_quality",
        input_data={
            "source": "訓練流程 V2",
            "target": "品質保證",
            "description": "auto-inferred relationship",
        },
        expected_verdict="fail",
        reason="自動生成的佔位符，完全沒有具體場景",
    ),
    TestCase(
        name="A 影響 B（只說了方向沒說場景）",
        capability="impact_quality",
        input_data={
            "source": "安全機制",
            "target": "V2 上線狀態",
            "description": "安全機制影響 V2 上線狀態",
        },
        expected_verdict="fail",
        reason="只重複了名稱，沒有具體說改了什麼、要檢查什麼",
    ),
]


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

@dataclass
class RunResult:
    test_name: str
    expected: str
    actual: str
    correct: bool
    latency_ms: int
    raw_response: dict[str, Any]


@dataclass
class CapabilityReport:
    capability: str
    total: int
    correct: int
    accuracy: float
    avg_latency_ms: int
    stability: float  # across N runs, how often same answer
    results: list[RunResult] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)


def run_single_test(
    llm, test: TestCase, run_id: int, thinking_budget: int = 0
) -> RunResult:
    """Run a single test case and return the result."""

    if test.capability == "l2_three_questions":
        system = L2_THREE_QUESTION_SYSTEM
        user_msg = (
            f"Entity:\n"
            f"  name: {test.input_data['name']}\n"
            f"  summary: {test.input_data['summary']}\n"
            f"  tags: {json.dumps(test.input_data['tags'], ensure_ascii=False)}"
        )
        schema = L2ThreeQuestionResult

    elif test.capability == "incremental_routing":
        system = INCREMENTAL_ROUTING_SYSTEM
        entities_str = "\n".join(
            f"  - id: {e['id']}, name: {e['name']}, summary: {e['summary']}"
            for e in test.input_data["existing_entities"]
        )
        user_msg = (
            f"新資訊：\n{test.input_data['new_info']}\n\n"
            f"現有 L2 概念：\n{entities_str}"
        )
        schema = IncrementalRoutingResult

    elif test.capability == "summary_language":
        system = SUMMARY_LANGUAGE_SYSTEM
        user_msg = (
            f"Entity:\n"
            f"  name: {test.input_data['name']}\n"
            f"  summary: {test.input_data['summary']}"
        )
        schema = SummaryLanguageResult

    elif test.capability == "impact_quality":
        system = IMPACT_QUALITY_SYSTEM
        user_msg = (
            f"Relationship:\n"
            f"  source: {test.input_data['source']}\n"
            f"  target: {test.input_data['target']}\n"
            f"  description: {test.input_data['description']}"
        )
        schema = ImpactQualityResult

    else:
        raise ValueError(f"Unknown capability: {test.capability}")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    start = time.monotonic()
    try:
        extra_kwargs = {}
        if thinking_budget and thinking_budget > 0:
            extra_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
        result = llm.chat_structured(
            messages=messages,
            response_schema=schema,
            temperature=0.1,
            **extra_kwargs,
        )
        latency = int((time.monotonic() - start) * 1000)
        actual_verdict = result.action if hasattr(result, "action") else result.verdict
        raw = result.model_dump()
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        actual_verdict = f"ERROR: {e}"
        raw = {"error": str(e)}

    return RunResult(
        test_name=f"{test.name} (run {run_id})",
        expected=test.expected_verdict,
        actual=actual_verdict,
        correct=(actual_verdict == test.expected_verdict),
        latency_ms=latency,
        raw_response=raw,
    )


def run_benchmark(n_runs: int = 3, thinking_budget: int = 0, model_override: str = "", temp_override: float | None = None):
    """Run all test cases N times each and produce a report."""
    thinking_label = f" + thinking({thinking_budget})" if thinking_budget else ""
    print("=" * 60)
    print(f"  Semantic Gate Benchmark{thinking_label}")
    print(f"  Runs per test: {n_runs}")
    print("=" * 60)

    llm = create_llm_client()
    if model_override:
        llm.model = model_override
    if temp_override is not None:
        llm.default_temperature = temp_override
    print(f"\n  Model: {llm.model}")
    print(f"  Temperature: {llm.default_temperature}")
    if thinking_budget:
        print(f"  Thinking budget: {thinking_budget} tokens")
    print()

    all_tests = {
        "l2_three_questions": L2_TEST_CASES,
        "incremental_routing": INCREMENTAL_ROUTING_TEST_CASES,
        "summary_language": SUMMARY_LANGUAGE_TEST_CASES,
        "impact_quality": IMPACT_QUALITY_TEST_CASES,
    }

    reports: list[CapabilityReport] = []

    for cap_name, tests in all_tests.items():
        print(f"\n{'─' * 60}")
        print(f"  Capability: {cap_name}")
        print(f"  Test cases: {len(tests)}")
        print(f"{'─' * 60}")

        all_results: list[RunResult] = []
        # Track per-test stability: test_name -> list of verdicts
        stability_map: dict[str, list[str]] = {}

        for test in tests:
            stability_map[test.name] = []
            for run_id in range(1, n_runs + 1):
                result = run_single_test(llm, test, run_id, thinking_budget)
                all_results.append(result)
                stability_map[test.name].append(result.actual)

                mark = "✅" if result.correct else "❌"
                print(
                    f"  {mark} {result.test_name}: "
                    f"expected={result.expected}, got={result.actual} "
                    f"({result.latency_ms}ms)"
                )

        # Calculate metrics
        correct_count = sum(1 for r in all_results if r.correct)
        total_count = len(all_results)

        # Stability: for each test, are all N runs the same?
        stable_tests = sum(
            1 for verdicts in stability_map.values()
            if len(set(verdicts)) == 1
        )
        stability = stable_tests / len(stability_map) if stability_map else 0

        avg_latency = (
            sum(r.latency_ms for r in all_results) // total_count
            if total_count
            else 0
        )

        mismatches = [
            f"  {r.test_name}: expected={r.expected}, got={r.actual}"
            for r in all_results
            if not r.correct
        ]

        report = CapabilityReport(
            capability=cap_name,
            total=total_count,
            correct=correct_count,
            accuracy=correct_count / total_count if total_count else 0,
            avg_latency_ms=avg_latency,
            stability=stability,
            results=all_results,
            mismatches=mismatches,
        )
        reports.append(report)

    # Final summary
    print("\n" + "=" * 60)
    print("  BENCHMARK SUMMARY")
    print("=" * 60)

    overall_correct = 0
    overall_total = 0

    for r in reports:
        overall_correct += r.correct
        overall_total += r.total
        status = "✅ PASS" if r.accuracy >= 0.85 else "❌ FAIL"
        stability_str = f"{r.stability:.0%}"
        print(
            f"\n  {r.capability}:"
            f"\n    Accuracy:  {r.accuracy:.0%} ({r.correct}/{r.total}) {status}"
            f"\n    Stability: {stability_str} (same answer across {n_runs} runs)"
            f"\n    Latency:   {r.avg_latency_ms}ms avg"
        )
        if r.mismatches:
            print("    Mismatches:")
            for m in r.mismatches:
                print(f"      {m}")

    overall_acc = overall_correct / overall_total if overall_total else 0
    print(f"\n{'─' * 60}")
    print(f"  Overall: {overall_acc:.0%} ({overall_correct}/{overall_total})")
    print(f"{'─' * 60}")

    # Verdict
    all_pass = all(r.accuracy >= 0.85 for r in reports)
    all_stable = all(r.stability >= 0.80 for r in reports)

    print("\n  VERDICT:")
    if all_pass and all_stable:
        print("  ✅ Gemini Flash 2.5 Lite CAN handle semantic governance")
        print("     → Proceed with SemanticGate implementation")
    elif all_pass:
        print("  ⚠️  Accuracy OK but stability issues")
        print("     → May need few-shot examples or higher temperature tuning")
    else:
        failing = [r.capability for r in reports if r.accuracy < 0.85]
        print(f"  ❌ CANNOT handle: {', '.join(failing)}")
        print("     → Need stronger model or fundamentally different approach")

    # Dump full results for analysis
    output_path = os.path.join(
        os.path.dirname(__file__), "benchmark_results.json"
    )
    dump = []
    for r in reports:
        dump.append({
            "capability": r.capability,
            "accuracy": r.accuracy,
            "stability": r.stability,
            "avg_latency_ms": r.avg_latency_ms,
            "mismatches": r.mismatches,
            "results": [
                {
                    "test": res.test_name,
                    "expected": res.expected,
                    "actual": res.actual,
                    "correct": res.correct,
                    "latency_ms": res.latency_ms,
                    "raw": res.raw_response,
                }
                for res in r.results
            ],
        })
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)
    print(f"\n  Full results saved to: {output_path}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    thinking = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    model = sys.argv[3] if len(sys.argv) > 3 else ""
    temp = float(sys.argv[4]) if len(sys.argv) > 4 else None
    run_benchmark(n_runs=n, thinking_budget=thinking, model_override=model, temp_override=temp)
