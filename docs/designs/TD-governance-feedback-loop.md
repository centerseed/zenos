---
type: TD
status: Draft
linked_spec: SPEC-governance-feedback-loop
created: 2026-03-28
updated: 2026-03-28
---

# Technical Design: 治理品質回饋迴路（P0 + P1）

## 背景

SPEC-governance-feedback-loop 識別了 ZenOS 治理管線的兩個根本缺口：

1. **寫入時無分層強制**：capture 流程可直接建 L2 entity 而不觸發三問判斷，導致 ontology 從第一天退化成文件索引
2. **寫入後無品質回饋**：blindspot 沉默累積、impacts 斷鏈、過時文件污染均無自動偵測

本 TD 設計 P0-1、P0-2、P1-1、P1-2、P1-3 共 5 項需求的技術方案。

---

## 現有架構盤點

### 相關程式碼位置

| 層 | 路徑 | 職責 |
|----|------|------|
| interface | `src/zenos/interface/tools.py` | MCP tools：write / confirm / analyze |
| application | `src/zenos/application/ontology_service.py` | upsert_entity、confirm 邏輯 |
| application | `src/zenos/application/governance_service.py` | GovernanceService，所有 analyze check |
| domain | `src/zenos/domain/governance.py` | 純函數：品質規則、staleness、blindspot、impacts validity |
| infrastructure | `src/zenos/infrastructure/sql_repo.py` | SqlTaskRepository（支援 linked_entity 過濾）|

### 現有 analyze check_type

| check_type | 產出 |
|-----------|------|
| quality | 14 項品質檢查，含 `l2_impacts_target_validity`（已有）|
| staleness | StalenessWarning 列表（以更新時間判斷）|
| blindspot | 從 ontology 結構推斷盲點 |
| all | 以上全部 + KPI snapshot |

### 現有 impacts gate（確認層）

`confirm(collection="entities")` 在 `OntologyService.confirm_entity_active()` 中強制檢查：
- entity.type == MODULE 且 status in (draft, stale)
- 必須有 ≥1 條具體 impacts（含 `→` 的描述）
- **現有缺口**：gate 僅在 confirm 時觸發，write 時無分層路由強制

### 現有 impacts 目標有效性檢查（P1-2 部分已實作）

`governance.check_impacts_target_validity()` 在 `run_quality_check()` 中呼叫：
- 檢查 impacts 目標 entity 是否存在
- 檢查目標 entity.status 是否在 `_INVALID_TARGET_STATUSES = {stale, draft, completed}`
- 產出：`results["quality"]["l2_impacts_validity"]`
- **現有缺口**：輸出格式不含具體斷鏈描述與建議動作，前端無法直接呈現

---

## P0-1：Capture 強制分層路由

### 問題根因

agent 呼叫 `write(collection="entities", data={type: "module", ...})` 時，server 接受任何 MODULE entity 並存成 draft，不要求 agent 回答三問或提供 impacts 草稿。三問邏輯存在於 skill 層，不在 server 層，因此 agent 可以跳過。

### 設計方案：write 時三問驗證門

**原則**：智慧邏輯在 server 端強制，不靠 caller skill 自律。

#### 新增欄位 `layer_decision`

在 `write(collection="entities", type="module")` 時，新增選填欄位 `layer_decision`：

```python
layer_decision: dict | None = None
# 格式：
# {
#   "q1_persistent": bool,        # 這個概念跨時間存活？不是一次性研究？
#   "q2_cross_role": bool,        # 跨越 ≥2 個不同角色/職能都在用？
#   "q3_company_consensus": bool, # 是公司共識概念，不是個人判斷？
#   "impacts_draft": str          # 至少一條候選 impacts（可以是草稿）
# }
```

#### Server 端行為（OntologyService.upsert_entity）

```
write(entities, type=module) 收到請求
    ↓
是否提供 layer_decision？
    │
    ├── 否，且 force=False（預設）：
    │       回傳 LAYER_DECISION_REQUIRED
    │       包含三問提示 + 範例 impacts 格式
    │
    ├── 否，且 force=True + manual_override_reason：
    │       允許寫入（維持現有行為，支援 admin bypass）
    │       warnings 中記錄 "bypass layer_decision check"
    │
    └── 是：
            三問全通過（q1 & q2 & q3 全 True）→ 正常寫入 draft
            任一三問未通過 → 回傳 LAYER_DOWNGRADE_SUGGESTED
                降級路徑：
                - q1=False（非持久） → 建議改為 document 並掛在相關 L2 的 sources
                - q2=False（單角色） → 建議改為 L3 entity（type=goal/role/project）
                - q3=False（非共識） → 建議改為 document type
```

#### LAYER_DECISION_REQUIRED 回傳格式

```json
{
  "error": "LAYER_DECISION_REQUIRED",
  "message": "寫入 L2 entity 前必須完成分層判斷",
  "layer_decision_prompt": {
    "q1": "這個概念跨越時間存活嗎？6個月後仍相關，不是一次性研究/報告？(true/false)",
    "q2": "這個概念跨越 ≥2 個不同角色或職能嗎？例如 PM + Developer 都需要理解它？(true/false)",
    "q3": "這是公司的共識概念嗎？不是個人判斷或技術實作細節？(true/false)",
    "impacts_draft_hint": "若三問全通過，請提供至少一條候選 impacts，格式：'A 改了什麼→B 的什麼要跟著看'"
  },
  "downgrade_options": [
    {"type": "document", "reason": "若是一次性研究，改為 document 並掛在相關 L2 的 sources"},
    {"type": "L3", "reason": "若是技術細節或單角色知識，改為 goal/role/project entity"}
  ]
}
```

#### 批次冷啟動（/zenos-capture）的處理

批次匯入時逐個三問會阻塞流程。設計方案：**允許批次但附標記**。

```
/zenos-capture 產出 L2 候選清單
    ↓
每個候選帶 layer_decision（三問結果 + impacts_draft）
    ↓
write(entities, type=module, layer_decision={...})
    → 三問全通過 → 寫入 draft
    → 未通過 → 寫入 document（降級）或 跳過並記錄
    ↓
capture 完成後輸出：
    - confirmed_l2: [通過三問的 L2 candidates]
    - downgraded: [被降級的候選 + 降級原因]
    - skipped: [無法判斷的候選]
```

capture skill 端一次給 LLM 所有候選（批次判斷），由 LLM 對每個候選填答三問。server 端逐個驗證三問結果，不需要 server 端跑 LLM。

**效能**：write 端的驗證是純欄位檢查（O(1) per entity），LLM 呼叫集中在 capture skill 端，可批次處理 N 個候選一次 API call。

#### 實作變更

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `ontology_service.py` | 修改 `upsert_entity()` | 加入 layer_decision 驗證邏輯（新增 `_validate_l2_layer_decision` 方法）|
| `interface/tools.py` | 修改 write tool 描述 | 新增 `layer_decision` 欄位說明 |
| `domain/models.py` | 可選：新增 `LayerDecision` dataclass | 結構化三問回應 |

**注意**：capture skill（`.claude/skills/`）也需更新，但屬 skill 層，不屬本 TD 的 server 實作範疇。

---

## P0-2：冷啟動後的品質校正優先級清單

### 設計方案：三維度無 LLM 品質評分

在 `analyze(check_type="quality")` 的輸出中新增 `quality_correction_priority` 子物件。

#### 三個評分維度

**維度 1：Impacts 模糊度（0-2分）**

| 狀態 | 分數 | 判斷條件 |
|------|------|---------|
| 有具體 impacts（含 `→` 的描述） | 0 | `_is_concrete_impacts_description(rel.description)` |
| 有 impacts 但不具體（無 `→`） | 1 | rel.type == "impacts" but no `→` |
| 無 impacts | 2 | no outgoing impacts relationships |

**維度 2：Summary 通用性（0-2分）**

| 狀態 | 分數 | 判斷條件 |
|------|------|---------|
| 含技術術語或具體描述 | 0 | `_has_technical_summary(summary)` == True |
| summary 長度足夠但無技術術語 | 1 | len(summary) >= 30 and `_has_technical_summary` == False |
| summary 過短（< 30 字）或空 | 2 | len(summary) < 30 |

**維度 3：三問信心度（0-2分，5個等級）**

| 狀態 | 分數 | 判斷條件 |
|------|------|---------|
| confirmed（active）且 why + how 不空 | 0 | status == "active" and tags.why and tags.how |
| draft + layer_decision 有附上（P0-1 產出）| 0.5 | status == "draft" and details.get("layer_decision") |
| draft + why + how 不空（人工填寫 tags）| 1.0 | status == "draft" and tags.why and tags.how and no layer_decision |
| draft + why 或 how 其一空 | 1.5 | status == "draft" and bool(tags.why) != bool(tags.how) |
| draft + why 和 how 都空 | 2.0 | status == "draft" and not tags.why and not tags.how |

**設計意圖**：P0-1 上線後的冷啟動 entity（有 layer_decision）比舊有 entity（無 layer_decision）得分更低，反映「有三問紀錄」本身就是一種品質保證；讓這個維度在冷啟動情境下仍有鑑別力，而非對所有 draft entity 一視同仁。

#### 優先級分數計算

```python
score = (
    impacts_vagueness * 0.5 +     # 最重要：impacts 是 L2 存在的核心
    summary_generality * 0.3 +    # 次重要：summary 品質決定搜尋有效性
    three_q_confidence * 0.2      # 補充：分層信心度（5 等級，0/0.5/1.0/1.5/2.0）
)
# 分數範圍 0.0 ~ 2.0，越高越需要優先校正
```

#### 輸出格式（加進 analyze quality 回傳）

```json
{
  "quality": {
    "quality_correction_priority": {
      "total_l2_entities": 12,
      "ranked": [
        {
          "entity_id": "abc123",
          "entity_name": "ERP Adapter 策略",
          "score": 1.8,
          "dimensions": {
            "impacts_vagueness": 2,
            "summary_generality": 1,
            "three_q_confidence": 1
          },
          "top_repair_action": "補充至少 1 條具體 impacts（A 改了什麼→B 的什麼要跟著看）"
        }
      ],
      "needs_immediate_review": 3
    }
  }
}
```

`needs_immediate_review` = score > 1.5 的 entity 數量。

#### 實作變更

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `domain/governance.py` | 新增函數 `compute_quality_correction_priority()` | 純函數，輸入 entities + relationships，輸出排序清單 |
| `application/governance_service.py` | 修改 `run_quality_check()` | 呼叫新函數並附加到 QualityReport |
| `domain/models.py` | 修改 `QualityReport` | 加入 `quality_correction_priority: list[dict] | None` 欄位 |

---

## P1-1：Task 信號 → Blindspot 管道

### 問題

GovernanceService 目前無法讀取 TaskRepository，blindspot 分析僅從 ontology 結構推斷，不讀 task history。

### 設計方案

#### 架構變更：GovernanceService 注入 TaskRepository

```python
class GovernanceService:
    def __init__(
        self,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository | None = None,
        protocol_repo: ProtocolRepository | None = None,
        blindspot_repo: BlindspotRepository | None = None,
        task_repo: TaskRepository | None = None,  # ← 新增
    ) -> None:
        ...
        self._tasks = task_repo
```

`tools.py` 的 `_ensure_services()` 也需同步傳入 `task_repo`。

#### 「類似問題」相似度判斷（無 LLM）

使用 keyword-based token overlap：

**問題信號關鍵字集（PROBLEM_SIGNAL_KEYWORDS）**：

```python
PROBLEM_SIGNAL_KEYWORDS = {
    # 中文
    "已知問題", "已知限制", "workaround", "繞過", "失敗", "無法", "錯誤",
    "bug", "問題", "限制", "例外", "不支援", "timeout", "衝突",
    # 英文
    "workaround", "known issue", "fail", "error", "bug", "limit",
    "exception", "not supported", "conflict", "broken", "issue"
}
```

**相似度計算（task 兩兩比對）**：

```python
def _task_problem_tokens(task: Task) -> set[str]:
    """從 task 的 result + description 中萃取問題相關詞彙。"""
    text = f"{task.result or ''} {task.description or ''}".lower()
    return {kw for kw in PROBLEM_SIGNAL_KEYWORDS if kw in text}

def _tasks_are_similar(t1: Task, t2: Task, threshold: int = 2) -> bool:
    """兩個 task 的問題詞彙重疊 >= threshold 則視為類似問題。"""
    tokens1 = _task_problem_tokens(t1)
    tokens2 = _task_problem_tokens(t2)
    return len(tokens1 & tokens2) >= threshold
```

#### 閾值 N 的設計

| 專案 task 規模 | N（觸發 blindspot 建議的最小 task 數）|
|--------------|-------------------------------------|
| < 20 tasks   | 2 |
| 20 ~ 100 tasks | 3 |
| > 100 tasks  | 5 |

動態調整邏輯：

```python
def _blindspot_threshold(entity_task_count: int) -> int:
    if entity_task_count < 20:
        return 2
    elif entity_task_count <= 100:
        return 3
    else:
        return 5
```

#### 查詢範圍

- 查詢 status in (done, cancelled)（已完成或放棄的 task 才有 result 信號）
- 過濾 linked_entities 包含目標 entity_id
- 每個 entity 最多取最近 200 筆（分頁防止超大專案拖慢）

#### 效能考量

- 不做全域掃描，而是對每個 L2 entity 獨立查詢（`list_tasks(linked_entity=entity_id, status=["done","cancelled"], limit=200)`）
- L2 entity 通常 < 50 個，每個查詢走 SQL index（linked_entities GIN index），預期 < 50ms/entity
- 整體 `infer_blindspots_from_tasks()` 在 100 個 L2 entity 下預估 < 5s（可接受，analyze 是非實時操作）

#### 輸出整合進 analyze blindspot

新增 `infer_blindspots_from_tasks()` 方法，產出格式與現有 blindspot 建議一致：

```json
{
  "blindspots": {
    "blindspots": [...],
    "count": 5,
    "task_signal_suggestions": [
      {
        "entity_id": "abc123",
        "entity_name": "排班模組",
        "pattern_summary": "3 張 task 提到 'LLM JSON 格式' 問題",
        "matched_tasks": ["task-001", "task-042", "task-077"],
        "suggested_blindspot": {
          "description": "排班模組 LLM JSON 格式不穩定，agent 需每次驗證並 fallback",
          "severity": "yellow",
          "suggested_action": "在 sources 中記錄 workaround 步驟，或更新 L2 summary 加入已知限制"
        }
      }
    ]
  }
}
```

#### 實作變更

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `application/governance_service.py` | 新增方法 `infer_blindspots_from_tasks()` | 依賴 self._tasks |
| `domain/governance.py` | 新增函數 `_task_problem_tokens()`, `_tasks_are_similar()`, `_blindspot_threshold()` | 純函數 |
| `interface/tools.py` | 修改 `_ensure_services()` | 傳入 task_repo 給 GovernanceService |
| `interface/tools.py` | 修改 `analyze(check_type="blindspot")` 區塊 | 呼叫新方法並合併輸出 |

---

## P1-2：Impacts 斷鏈自動偵測

### 現有狀態

`check_impacts_target_validity()` 已在 `run_quality_check()` 中呼叫，且結果存入 `results["quality"]["l2_impacts_validity"]`。現有函數已正確處理：
- 目標 entity 不存在
- 目標 entity.status in {stale, draft, completed}

### 現有缺口

1. 輸出的 `broken_impacts` 列表中缺少具體 impacts 描述文字（只有 relationship_id），前端/agent 難以理解「斷了什麼」
2. 沒有建議動作（suggested_action）
3. 在 QualityReport 的 check items 中僅有 pass/fail，不展開具體哪條斷鏈

### 設計方案：擴充輸出格式

#### 修改 `check_impacts_target_validity()` 回傳結構

```python
# domain/governance.py

def check_impacts_target_validity(...) -> list[dict]:
    # 每個斷鏈 entry 的新格式：
    {
        "source_entity_id": str,
        "source_entity_name": str,
        "broken_impacts": [
            {
                "relationship_id": str | None,
                "impacts_description": str,       # ← 新增：具體 impacts 描述
                "target_entity_id": str,
                "target_entity_name": str,         # ← 新增：目標名稱
                "reason": "target_missing" | "target_stale" | "target_draft",  # ← 結構化原因
                "suggested_action": str            # ← 新增：建議動作
            }
        ]
    }
```

**建議動作（suggested_action）生成規則**：

| reason | suggested_action |
|--------|-----------------|
| target_missing | `"目標 entity 已不存在，建議移除此 impacts 關聯"` |
| target_stale | `"目標 entity 已標記為 stale，建議確認是否有新的替代 entity，或更新 impacts 目標"` |
| target_draft | `"目標 entity 仍為 draft，建議先 confirm 目標 entity，或暫緩此 impacts"` |

#### analyze 輸出整合

`results["quality"]["l2_impacts_validity"]` 已存在，格式升級後自動生效，無需改 tools.py 的 analyze 路由。

#### 新增 check_type `"impacts"` 做精確查詢

允許 agent 只跑 impacts 檢查：`analyze(check_type="impacts")`

```python
if check_type in ("all", "quality", "impacts"):
    validity_report = await governance_service.check_impacts_target_validity()
    results.setdefault("quality", {})["l2_impacts_validity"] = validity_report
```

#### 實作變更

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `domain/governance.py` | 修改 `check_impacts_target_validity()` | 擴充 broken_impacts 欄位，加入 target_entity_name, impacts_description, reason, suggested_action |
| `application/governance_service.py` | 修改 `check_impacts_target_validity()` | 傳入 entity_map 讓函數能查目標名稱 |
| `interface/tools.py` | 修改 `analyze()` | 新增 `"impacts"` check_type |

---

## P1-3：過時文件主動標記

### 設計方案：三類一致性信號（無 LLM）

冷啟動後，對每個 document entity 從以下三類信號判斷是否可能過時：

#### 信號 1：版本號衝突（跨文件比對）

同一 entity 下（same linked_entity_ids）的多份文件若出現版本號，比對最大版本與其他版本的差距。

```python
_VERSION_PATTERN = re.compile(r'v(\d+)\.(\d+)', re.IGNORECASE)

def _extract_version(text: str) -> tuple[int, int] | None:
    """從 title 或 summary 中萃取版本號，回傳 (major, minor)。"""
    m = _VERSION_PATTERN.search(text)
    return (int(m.group(1)), int(m.group(2))) if m else None
```

若同一 entity 的文件中，某份文件版本比最新版低 ≥ 2 個 major，標記 `reason="version_lag"`。

#### 信號 2：互相矛盾（title/summary 關鍵詞對立）

偵測同一 entity 下兩份文件的 summary 中出現語意對立的詞對：

```python
CONTRADICTION_PAIRS = [
    ("不支援", "支援"),
    ("廢棄", "推薦"),
    ("已移除", "現有"),
    ("deprecated", "recommended"),
    ("removed", "current"),
]
```

若對立詞對出現在同一 entity 的不同文件，標記 `reason="contradictory_signal"`。

#### 信號 3：時間老化（輔助信號）

last_modified > 180 天（已在 staleness 中處理），但若文件 linked_entity 的 L2 entity 在近 90 天有更新，則文件更可能過時（L2 改了但文件沒改）。標記 `reason="entity_updated_but_doc_stale"`。

#### 輸出整合進 analyze staleness

```json
{
  "staleness": {
    "warnings": [...],
    "count": 5,
    "document_consistency_warnings": [
      {
        "document_id": "doc-abc",
        "document_title": "排班模組設計文件 v1.2",
        "linked_entity_id": "abc123",
        "linked_entity_name": "排班模組",
        "reason": "version_lag",
        "detail": "發現更新版本 v3.0 存在於同一模組下的其他文件",
        "suggested_action": "確認此文件是否已被 v3.0 文件取代，若是請走 archive/supersede 流程"
      }
    ]
  }
}
```

#### 新增 check_type `"document_consistency"` 做精確查詢

允許 agent 只跑文件一致性檢查：`analyze(check_type="document_consistency")`

#### 實作變更

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `domain/governance.py` | 新增函數 `detect_stale_documents_from_consistency()` | 純函數，輸入 entities（含 documents）+ relationships，輸出 consistency warnings |
| `application/governance_service.py` | 修改 `run_staleness_check()` | 呼叫新函數並合併到回傳結果 |
| `interface/tools.py` | 修改 `analyze()` | 新增 `"document_consistency"` check_type |

---

## Spec 介面合約

| 需求 | 介面 | 關鍵參數 | Done Criteria 對應 |
|-----|------|---------|-------------------|
| P0-1 | `write(entities, type=module)` | `layer_decision: {q1, q2, q3, impacts_draft}` | DC-1: 無 layer_decision 且 force=False → 回 LAYER_DECISION_REQUIRED |
| P0-1 | `write(entities, type=module)` | `layer_decision.q1/q2/q3` | DC-2: 任一 False → 回 LAYER_DOWNGRADE_SUGGESTED 含降級路徑 |
| P0-1 | `write(entities, type=module, force=True)` | `manual_override_reason` | DC-3: force bypass 需 manual_override_reason，warning 記錄 |
| P0-2 | `analyze(check_type="quality")` | 回傳 `quality_correction_priority.ranked[]` | DC-4: 含三個維度分數（impacts_vagueness, summary_generality, three_q_confidence）|
| P0-2 | `analyze(check_type="quality")` | `ranked[].score`（浮點 0.0~2.0）| DC-5: 按 score 降序排列 |
| P1-1 | `analyze(check_type="blindspot")` | 回傳 `task_signal_suggestions[]` | DC-6: 每個 suggestion 含 matched_tasks[] 和 suggested_blindspot |
| P1-1 | GovernanceService | `task_repo` 注入 | DC-7: GovernanceService 初始化時接受 task_repo 參數 |
| P1-2 | `analyze(check_type="quality"/"impacts")` | `l2_impacts_validity[].broken_impacts[].reason` | DC-8: reason 為結構化 enum（target_missing/target_stale/target_draft）|
| P1-2 | `check_impacts_target_validity()` | 回傳含 `suggested_action` 欄位 | DC-9: 每條斷鏈都有 suggested_action |
| P1-3 | `analyze(check_type="staleness"/"document_consistency")` | 回傳 `document_consistency_warnings[]` | DC-10: 每條 warning 含 reason 和 suggested_action |

---

## 風險與不確定性

### 我不確定的地方

- **P1-1 keyword matching 的誤報率**：PROBLEM_SIGNAL_KEYWORDS 可能過於寬泛，導致「問題」這個詞出現在任何 task 的 result 裡都被觸發。需要在 paceriz 的真實 task 資料上驗證閾值設定（已保守設為 N=2 最小情況）。
- **P1-3 矛盾詞對的精確度**：靜態 CONTRADICTION_PAIRS 覆蓋的場景有限，對中文同義詞的處理不足。這是一個「能偵測一部分」而非「能偵測所有」的設計，可接受。

### 可能的替代方案

- **P0-1 替代方案**：在 capture skill 端加入三問流程（不改 server）→ 拒絕，因為 skill 層繞過是現有問題的根因
- **P0-2 替代方案**：用 LLM 評估 summary 品質 → 拒絕，SPEC 明確要求不依賴額外 LLM 呼叫
- **P1-1 替代方案**：用 embedding 做語意相似度 → 拒絕，成本過高且現階段不需要

### 需要用戶確認的決策

- **P0-1**：現有 capture 已產出大量 L2 entities（paceriz），本次變更對**已存在的 draft entities** 不溯及既往（只對新 write 操作生效）。確認這個判斷正確嗎？
- **P0-2 加權設定**：impacts_vagueness=0.5, summary_generality=0.3, three_q_confidence=0.2。是否合理？還是希望三個維度等權（0.33）？

### 最壞情況

- P0-1 的 `force=True` bypass 在 agent 端被濫用（agent 學會每次都加 `force=True` 來跳過三問）。緩解：force bypass 會記錄在 warnings，analyze 的 l2_repairs 會標記 `manual_override_reason`，可被治理回路偵測。

---

## 實作依賴順序與平行性

```
P1-2（impacts 斷鏈）              P0-2（品質優先級）
    ↓ 擴充現有函數，無新依賴          ↓ 擴充現有函數，無新依賴
    可立即實作                        可立即實作

P0-1（分層路由 write gate）       P1-3（文件一致性）
    ↓ 修改 upsert_entity              ↓ 新增 governance 函數
    可立即實作                        可立即實作

P1-1（task 信號管道）
    ↓ 依賴 GovernanceService 注入 task_repo
    需先確認 tools.py 初始化完成後實作
```

**建議實作順序**：

1. **Phase A（平行）**：P1-2 + P0-2（純 domain 擴充，不改介面）
2. **Phase B（平行）**：P0-1 + P1-3（修改 write gate + staleness check）
3. **Phase C**：P1-1（架構注入 + domain 新函數）

Phase A 和 B 可以讓 Developer 平行處理。Phase C 依賴 tools.py 的初始化變更，放最後。

---

## 影響範圍

### 新增/修改的檔案

| 檔案 | 變更類型 | 涉及需求 |
|------|---------|---------|
| `src/zenos/domain/governance.py` | 新增 3 個函數，修改 1 個函數 | P0-2, P1-1, P1-2, P1-3 |
| `src/zenos/application/governance_service.py` | 修改 3 個方法，新增 1 個方法 | P0-2, P1-1, P1-2, P1-3 |
| `src/zenos/application/ontology_service.py` | 修改 `upsert_entity()` | P0-1 |
| `src/zenos/domain/models.py` | 修改 `QualityReport`，可選新增 `LayerDecision` | P0-1, P0-2 |
| `src/zenos/interface/tools.py` | 修改 write 描述、analyze routing、GovernanceService 初始化 | P0-1, P1-1, P1-2, P1-3 |

### 影響的現有功能

- `write(entities, type=module)` **行為改變**（P0-1）：現有未帶 layer_decision 的呼叫會收到 LAYER_DECISION_REQUIRED。**影響 capture skill** — 需同步更新。
- `analyze(quality)` 輸出結構新增欄位（P0-2, P1-2）：向後相容（只新增，不移除）。
- `analyze(blindspot)` 輸出結構新增欄位（P1-1）：向後相容。
- `analyze(staleness)` 輸出結構新增欄位（P1-3）：向後相容。
- **不影響** confirm、search、get、task、read_source。
