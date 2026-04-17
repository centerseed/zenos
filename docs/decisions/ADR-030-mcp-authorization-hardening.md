---
doc_id: ADR-030-mcp-authorization-hardening
title: 決策紀錄：MCP Authorization Hardening — Workspace 契約收斂與權限測試強化
type: DECISION
ontology_entity: 身份與權限管理
status: Draft
version: "1.0"
date: 2026-04-10
supersedes: null
---

# ADR-030: MCP Authorization Hardening — Workspace 契約收斂與權限測試強化

## Context

`SPEC-identity-and-access`、`TC-identity-and-access`、`ADR-024`、`ADR-029` 已經把 ZenOS 的 MCP authorization runtime 切成三個核心軸線：

1. `active workspace context` 是所有權限判定的正式執行單位
2. API key 與 delegated JWT 是兩條不同 credential path，但都必須落到同一套 workspace / role / visibility runtime
3. 權限一致性必須由 server 端強制執行，agent 與 dashboard 只能消費過濾後結果

但目前 MCP 相關實作與測試有三個結構性問題：

1. **workspace 預設行為仍不穩定。**
   `SPEC-identity-and-access` 與 `ADR-024` 都要求「未指定 workspace 時預設回 home workspace」，但 `application/identity/workspace_context.py` 仍保留 shared member 預設進 shared workspace 的分支，導致 spec、dashboard 測試、MCP runtime 三者不一致。

2. **權限測試集中在 read-side visibility，沒有覆蓋完整 authorization 邊界。**
   `tests/interface/test_permission_isolation.py` 已經對 entity / task / blindspot 的可見性做了大量測試，但多數案例直接注入 ContextVar 或使用 `sharedPartnerId=None` 的單 workspace fixture，沒有真正覆蓋「同一 principal 在 home 是 owner、在 shared 是 guest/member」的核心模型。

3. **delegated JWT path 缺少真正的整合測試。**
   `ApiKeyMiddleware` 已支援 JWT delegated credential、`workspace_ids` claim 與粗粒度 `scopes`，但現有測試幾乎只覆蓋 API key 401/200 邊界與 decorator 純函式，沒有測到真正的 middleware → workspace projection → tool scope enforcement → visibility filtering 這條高風險鏈路。

結果是：MCP 層看似有不少權限測試，但真正容易出事故的「不同帳號、不同 credential、不同 workspace」路徑仍是薄弱區。

## Decision

### D1. 先收斂 contract，再補測試；不得在 contract 分裂狀態下擴寫更多 permission case

MCP authorization hardening 的第一原則是先讓下列三者重新對齊：

- `SPEC-identity-and-access`
- `ADR-024`
- `application/identity/workspace_context.py`

正式規則統一為：

- 無 `workspace_id` / 無 `X-Active-Workspace-Id` 時，**一律預設回 home workspace**
- `workspace_id` 是 MCP 正規切換入口
- shared workspace 只是 active workspace 的一種投影，不得成為 fallback 特例

在這個 contract 收斂完成前，不再新增更多建立在舊 fallback 假設上的 permission case。否則測試只會把錯誤行為固化成新的假契約。

同時，與 SSOT 衝突的舊 regression case 必須直接刪除或改寫，不得繼續保留：

- 不得再用測試保護「guest 在 shared workspace 可看到 restricted/confidential task」
- 不得再用測試保護「shared member 可透過 legacy `/role` 變成 owner」
- 不得再用測試保護「權限變更要靠重設 token 才生效」這種 setup 誤導語意

### D2. 把 MCP authorization 測試矩陣重構為四層，而不是繼續把案例堆進單一 isolation 檔

未來測試結構改為四層：

1. **Workspace Contract Layer**
   驗證 workspace resolution、active partner projection、workspace_context 回傳內容。

2. **Credential Boundary Layer**
   驗證 API key path 與 delegated JWT path 的 authentication / scope / workspace claim 行為。

3. **Authorization Matrix Layer**
   驗證 owner / member / guest 在 home/shared workspace 下對 entities / tasks / documents / blindspots 的 read/write/task 權限。

4. **Cross-Surface Consistency Layer**
   驗證 dashboard API 與 MCP tool 對同一 principal、同一 active workspace 的結果一致。

`tests/interface/test_permission_isolation.py` 保留，但只承擔 read-side visibility regression。新的 workspace / credential / mutation matrix 必須拆到獨立測試檔，避免單檔同時承擔所有授權語意。

### D3. delegated JWT path 視為 P0 boundary，測試等級提升到與 API key path 相同

`ADR-029` 的 delegated credential 不再視為「之後再補」的次要路徑。從本 ADR 起，JWT path 是 P0 授權邊界，最低要求如下：

- 無效 JWT / 過期 JWT / 找不到 principal → `401`
- `workspace_id` 不在 token `workspace_ids` claim 內 → `403`
- 缺少 `write` scope 呼叫 `write/confirm/journal_write/upload_attachment` → `FORBIDDEN`
- 缺少 `task` scope 呼叫 `task/plan` → `FORBIDDEN`
- JWT caller 在同一 partner 下切換 home/shared workspace，必須得到與 API key path 相同的 workspace projection 與資料裁切結果

scope 測試不得只停留在 decorator 單元測試，必須至少覆蓋一次「middleware + 真實 MCP tool handler」整合路徑。

### D4. 權限測試以 principal 視角建矩陣，不再以零散 partner fixture 拼裝

未來測試資料模型以「同一 principal 的多 workspace presence」為主，不再只用互不相干的 partner dict 拼裝：

- `Principal A / home workspace / owner`
- `Principal A / shared workspace / guest`
- `Principal B / shared workspace / owner`
- `Principal C / shared workspace / member`

每個 principal 測試時都要同時驗證：

- workspace resolution 後的 `workspaceRole`
- `authorizedEntityIds` 是否正確投影
- `current_partner_id` 是否正確指向 active workspace tenant
- `workspace_context.available_workspaces` 是否保留完整切換資訊

這樣才能覆蓋 `Prosumer-First` 模型真正的風險點：同一個 user 在不同 workspace 看到不同權限，而不是「guest 是另一種帳號」。

### D5. Guest mutation contract 納入 MCP P0 測試，而不是只留在 application service

目前 guest create guard 主要在 `OntologyService` 測試。從本 ADR 起，以下行為列為 MCP P0 測試：

- guest 在 shared workspace 可建立 task
- guest 在 shared workspace 可建立掛在授權 L2 下的 L3
- guest 建立 L3 預設寫回 active workspace
- guest 建立的 L3 預設 `visibility=public`
- guest 不可建立 L1 / L2
- guest 不可藉由 `workspace_id` 切到未授權 workspace 後寫入

也就是說，guest write contract 必須從 application layer 一路驗到 MCP tool surface，不能只測 service guard。

### D6. rollout 採兩階段：先修 contract 與測試骨架，再補 read/write matrix

MCP hardening rollout 分兩階段：

**Phase 1：Contract Alignment**

- 修正 `resolve_active_workspace_id()` 與相關測試，使 default 行為回 home workspace
- 補 `ApiKeyMiddleware` 的 JWT integration 測試骨架
- 補 `workspace_context` / `_apply_workspace_override` / ContextVar restore 測試

**Phase 2：Authorization Matrix**

- 補 owner/member/guest 在 home/shared workspace 的 read matrix
- 補 guest mutation 與 JWT scope matrix
- 補 dashboard API vs MCP cross-surface consistency matrix
- 清掉所有與 SSOT 衝突的 legacy permission regression case，避免錯誤行為被舊測試固化

在 Phase 1 完成前，不以「permission isolation 現有案例很多」宣稱 MCP authorization coverage 足夠。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| 繼續在 `test_permission_isolation.py` 疊更多案例 | 改動最少 | 檔案已混合 dashboard、MCP、guest subtree、legacy compatibility、task special case；再擴寫只會讓邊界更模糊 | 不能形成可維護的授權測試結構 |
| 只補 JWT decorator/unit tests，不做 middleware integration | 撰寫成本低 | 測不到 credential parsing、workspace claim 驗證、partner projection、tool wiring | 無法保護真正高風險路徑 |
| 先只修 runtime，不補測試矩陣 | 短期可快速交付 bug fix | contract 漂移會再次發生，之後無法判斷哪個行為才是正式契約 | 會重演目前 spec/runtime/test 分裂 |
| 把 guest/member/owner 視為三種不同帳號型別繼續測 | fixture 容易寫 | 違反 `active workspace context` 模型，測不到同一 principal 跨 workspace 切換風險 | 與 SPEC-identity-and-access 衝突 |

## Consequences

- 正面：
  - MCP authorization 的測試重心會從「單純可見性」提升到真正的 credential + workspace + role 邊界。
  - `home workspace` fallback 會重新成為唯一 SSOT，dashboard 與 MCP 不再各自解釋。
  - delegated JWT path 取得與 API key path 對等的測試保護，降低 federation rollout 風險。
  - 後續新增權限規則時，可以明確放入四層測試架構中的某一層，而不是繼續堆進單一大檔。

- 負面：
  - 需要重整既有測試檔結構，短期內測試改動量大於功能改動量。
  - 會暴露目前 runtime 與既有測試中的隱性矛盾，短期內可能出現一波測試失敗。
  - 團隊不能再用「read-side isolation 有測到」當作整體授權 coverage 的代理指標。

- 後續處理：
  - 若 Phase 1 修正後仍發現 dashboard 與 MCP projection 不一致，需另開 bugfix ADR 或 implementation task，不在本 ADR 內擴大 scope。
  - 若產品未來支援 3+ workspace，需在新的 membership model ADR 中同步更新本測試矩陣假設。

## Implementation

1. 修正 `src/zenos/application/identity/workspace_context.py` 的 default workspace resolution，使其與 `SPEC-identity-and-access`、`ADR-024` 一致。
2. 重寫 `tests/application/test_workspace_context.py`，以 SSOT 驅動 case，移除與正式契約衝突的舊假設。
3. 新增 `tests/interface/test_mcp_jwt_auth.py`，覆蓋 JWT delegated credential 的 middleware integration、scope enforcement、workspace_ids claim 驗證。
4. 新增 `tests/interface/test_mcp_workspace_authorization_matrix.py`，建立同一 principal 在 home/shared workspace 的 owner/member/guest 視角 read matrix。
5. 新增 `tests/interface/test_mcp_guest_mutation_contract.py`，覆蓋 guest task/L3 create success 與 L1/L2 reject、active workspace write-back、public visibility default。
6. 保留 `tests/interface/test_permission_isolation.py` 作為 read-side regression 檔，但把不屬於 visibility regression 的新案例移出。
7. 補一組 dashboard API vs MCP cross-surface consistency 測試，至少覆蓋 member 與 guest 在 shared workspace 的 entities/tasks 結果一致。
