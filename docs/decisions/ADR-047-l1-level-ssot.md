---
type: ADR
id: ADR-047
status: Superseded
ontology_entity: entity-model
created: 2026-04-23
updated: 2026-04-24
superseded_by: ADR-048-grand-ontology-refactor
supersedes_sections:
  - ADR-007#L1-單型定義
related:
  - ADR-028-plan-primitive
  - ADR-044-task-ownership-ssot-convergence
  - ADR-046-document-entity-boundary
---

# ADR-047: L1 判定收斂到 level、product_id 為唯一 API 語彙

> **2026-04-24 update：** L1 level axiom 與 L3-Action ownership tree 已由主 SPEC v2 + ADR-048 收斂為 runtime canonical。本 ADR 保留作歷史追溯。

## Context

ADR-044（2026-04-22）完成 Task/Plan ownership 從 `project_id` → `product_id` 的 rename，並把 DB 欄位、FK、server validation 全數切換。但治理規則仍殘留兩條 type-gating 條件，造成 L1 語意散裂：

1. **`product_id` validation 寫成「type ≠ product → INVALID_PRODUCT_ID」**
   - 位置：`governance_rules.py:940`、`application/action/task_service.py:91`、`plan_service.py:235`。
   - CRM bridge 同時在建 `type=company/person/deal, level=1` 的 L1 entity（`application/crm/crm_service.py:229,290,385`），但這些 entity 放到 `product_id` 會被上述規則 reject。
   - 使用者試圖用 CRM 建出的「原心生技」（type=company）建 plan，被 helper 報錯「需要 type=product 的 entity」，觸發本次 refactor。

2. **五份互不一致的 L1 白名單**散在 code 與 prompt：
   - `domain/knowledge/collaboration_roots.py`：`{product, company}`
   - `application/knowledge/ontology_service.py:_L1_TYPES`：`{product, company, person}`
   - `application/knowledge/ontology_service.py:_TYPE_TO_LEVEL`：只映射 `product → 1`，缺 company/person/deal
   - `interface/mcp/plan.py` / `interface/mcp/task.py` error message：口徑不一
   - `governance_rules.py` prompt：對 agent 說「type=product」

同一個「L1」概念有 5 種不同 gating 口徑，agent 與人類都無法形成穩定心智模型。

**設計意圖釐清（使用者對齊於 2026-04-23）：**
- L1 的本質是**共享邊界（collaboration root）**——可以整棵子樹分享給別的用戶的底層節點。
- `type` 是 UI 顯示 label，不是業務邏輯的分支來源。
- `level == 1 AND parent_id IS NULL` 是 L1 的**唯一判定條件**。
- agent 合約：任何 L1 entity id 都能當 `product_id`；agent 不查 type、server 不洩漏 type。

## Decision

### D1. `collaboration_roots` 收斂為 level-only 判定

將 `is_collaboration_root_entity` 改為：

```python
def is_collaboration_root_entity(entity) -> bool:
    if entity is None:
        return False
    level = getattr(entity, "level", None)
    parent_id = getattr(entity, "parent_id", getattr(entity, "parentId", None))
    return level == 1 and not parent_id
```

**刪除** `COLLABORATION_ROOT_TYPES` 常數與所有 type 白名單分支。

`level is None` 的 legacy 寬鬆判定**一併移除**——搭配 D4 的資料清洗 script，所有既有 L1 entity 必須有明確 `level=1`。

### D2. L1 允許任何 type（type 降為 UI label）

- 任何 type 只要滿足 `level=1 AND parent_id=null` 即為合法 L1。
- product / company / person / deal / goal / role 等所有 `EntityType` 都可以當 L1 的 type label。
- UI 按 type 決定 icon 與顯示，但不過濾——所有 L1 一律進 projects page。
- server 不針對 type 做業務分支；`EntityType` enum 的角色是「分類標籤」，不是「分類 gate」。

### D3. `project_id` alias 完全移除

- MCP tool `plan`、`task` 的 `project_id` 參數**刪除**（不保留 legacy alias）。
- `governance_rules.py` 移除所有 `project_id` 與 `PROJECT_STRING_IGNORED` 敘述。
- 錯誤碼 `MISSING_PRODUCT_ID` / `INVALID_PRODUCT_ID` 名稱保留（語意正確），但**觸發條件**改成「不是 L1 entity」，訊息文字不得再提 `type=product`。
- `linked_entities` strip 規則從「含 type=product entity」改成「含 L1 entity」——同樣使用 `is_collaboration_root_entity` 判定。
- Python dict 若傳 `project_id`，server 直接 reject（`INVALID_INPUT`），不靜默接受。

### D4. 既有資料清洗（one-off script）

產出 `scripts/backfill_entity_level.py`：

1. 掃 `zenos.entities`，找出 `level IS NULL` 的 entity。
2. 依 type 用 `_TYPE_TO_LEVEL`（擴充後含 company/person/deal→1、module→2、document/goal/role/project→3）補 level。
3. 遇無法推斷的 type → 報錯並列出，由人工決策。
4. Dry-run 先跑，確認影響筆數後才 commit。

完成後 `is_collaboration_root_entity` 可安全移除 `level is None` fallback。

### D5. `_TYPE_TO_LEVEL` 擴充為 label fallback

移到 `domain/knowledge/entity_levels.py` 集中管理（避免四散）：

```python
DEFAULT_TYPE_LEVELS: dict[str, int] = {
    "product": 1,
    "company": 1,
    "person": 1,
    "deal": 1,
    "module": 2,
    "document": 3,
    "goal": 3,
    "role": 3,
    "project": 3,
}
```

只在 `write(entities)` 且 caller 未傳 `level` 時使用。caller 顯式傳 `level` 一律以 caller 為準（label 與 level 可以自由組合）。

### D6. Guest guard 改用 level

`ontology_service._L1_TYPES` 刪除。Guest 建立 entity 的 guard 改成：

```python
if level == 1:
    raise ValueError("Guest partners cannot create L1 entities ...")
```

不再檢查 type 白名單。

### D7. UI 統一用 `isL1Entity(entity)` helper

Dashboard 新增 `dashboard/src/lib/entity-level.ts`：

```typescript
export function isL1Entity(entity: Entity): boolean {
  return entity.level === 1 && !entity.parentId;
}
```

所有 `entity.type === "product"` 的過濾判斷全部改用此 helper。視覺差異（icon/字型/大小）保留 type-based 分支，但**篩選邏輯**一律走 level。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **A. 保留 type 白名單，擴充到包含所有 CRM type** | 改動最小，不動 spec | 5 份白名單仍要同步，未來加 type 又要散改；本次觸發的 root cause 沒解 | 沒解決 SSOT 散裂問題，只是把坑挖大 |
| **B. 強制 L1 一律 type=product，CRM 不建獨立 L1 entity** | 語意最純 | 要重構 CRM bridge（把 company 降為 L2 掛在某 product 下），改動巨大；UX 變更（CRM 客戶不再是獨立知識節點） | 改動面過大，違反「最小必要 refactor」；且與「L1 = 共享邊界」的功能定義脫鉤 |
| **C（採用）. level 為 SSOT，type 為 label** | 一處判定、多 type 自由；對齊 entity.level 的既有設計 | 需要資料清洗補 level；需要同步更新多份 spec 與 prompt | 符合使用者設計意圖，且與 entity_level 搜尋參數的現有語意一致 |

## Consequences

### 正面
- **判定 SSOT**：`is_collaboration_root_entity` 與 `level` 欄位是唯一真相源，agent 與 UI 共用同一個判斷。
- **agent 合約乾淨**：MCP tool docstring 只說「任何 L1 entity id」，不洩漏 type 分類細節。
- **CRM entity 自動可用**：CRM 建出的 company/person entity 可以直接當 plan/task 的 `product_id`，不需另建 product entity。
- **L1 擴展免改 code**：未來新增 L1 label（例如 `partner`、`initiative`）只要擴充 `DEFAULT_TYPE_LEVELS`，不動任何判定邏輯。

### 負面
- **資料清洗一次性成本**：需要跑 backfill script + 驗證 DB 中無 `level=null` L1 entity。
- **Legacy alias 移除會破壞既有 caller**：任何還在傳 `project_id` 的舊 code / skill / script 會直接 reject。本次要求「最乾淨處理」，不保留 alias——必須全數改完才能部署。
- **AC test 全面更新**：`INVALID_PRODUCT_ID` 的觸發條件改了，所有 spec_compliance test 要同步。

### 後續處理
- 本 ADR accepted 後，ADR-007 的「L1 = product 單型」段落標記 superseded（見 `supersedes_sections`）。
- 若未來 CRM 擴充出新 entity type，只要在 `DEFAULT_TYPE_LEVELS` 加一行即可，不需新 ADR。
- `EntityType` enum 本身保留為開放 label 字典——新增 type label 不需要 spec 級決策，屬於 application 層 extension point。

## Implementation

詳細拆分與 gate 見 `docs/plans/PLAN-l1-level-ssot-refactor.md`。本 ADR 鎖定的 rollout 強制順序：

```
S01 SPEC/ADR
  → S02-data (backfill script + production apply)
  → [GATE A: SELECT count(*) FROM entities WHERE level IS NULL = 0]
  → S02-code (domain strict level check)
  → S03 Application
  → S04 Interface
  → S05 Infrastructure
  → [GATE B: backend deploy + health/log/e2e smoke]
  → S06 Dashboard UI
  → [GATE C: frontend deploy + full-site UI smoke]
  → S07 Skill SSOT（release/ + skills/governance/* mirror + skills/workflows/* mirror + sync_skills_from_release.py + ~/.claude/skills push）
  → [GATE D: governance_ssot_audit clean]
  → S08 Final QA + rollback drill + e2e 驗證
```

**Rollout 硬約束：**

- **GATE A 是 strict level code 的前置條件**：因為 D1 移除 `level is None` fallback，若 production DB 仍有 `level IS NULL` 的 L1 entity，部署 S02-code 之後會立即把它們判成非法 L1，造成 plan/task 功能中斷。backfill 必須在 production DB 完成、QA 獨立驗證 count=0，才能開工 S02-code。
- **GATE B/C 沿用 Architect SKILL Phase 3 部署規則**：health check + log 無 ERROR + 端到端 + UI 冒煙，任一失敗 → rollback 前一版。
- **GATE D 防 SSOT 分裂**：本次動到的 governance 文案不僅在 `skills/release/*` SSOT，更關鍵的是 `skills/governance/*` 與 `skills/workflows/*` 的專案根 mirror——這是 slash command 與 `governance_ssot_audit`（`src/zenos/application/knowledge/governance_ssot_audit.py:52`）實際讀取的位置。S07 必須完成雙向同步 + audit clean，才進 S08。

**Rollback plan（S08 Part D 執行前必須文件化）：**

1. Backend：Cloud Run 前一版 revision 重指派流量
2. Frontend：Firebase Hosting `hosting:clone <prev-version> live`
3. DB backfill：S02-data 留下 `(id, level)` snapshot；rollback 把 snapshot 的 rows 改回 null（對舊 code 無害——舊 code 不依賴 strict level）
4. Skill：`git revert` + `sync_skills_from_release.py` + 重推 `~/.claude/skills/`

**順序變更禁令：** S02-code 之後所有 strict level 相關 code 的部署若未通過 GATE A，rollout 立即停止，由 Architect 決定補 backfill 還是 rollback。
