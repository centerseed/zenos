---
doc_id: ADR-043-multi-tenant-deployment-architecture
title: 決策紀錄：Multi-Tenant 部署架構
type: DECISION
ontology_entity: Multi-Tenant 部署架構決策
status: Approved
version: "1.0"
date: 2026-04-21
supersedes: null
---

# ADR-043: Multi-Tenant 部署架構

## Context

ZenOS 早期曾有「一客戶一 Firebase Project」的 multi-tenant 構想，並留在 `docs/archive/specs/deferred-2026-03/SPEC-multi-tenant.md`。但 repo 與現行 spec 已經往另一條路徑演進：

- `SPEC-identity-and-access` 已把正式隔離單位定義成 `active workspace context`
- `ADR-024` 與 `ADR-029` 已把 MCP / Dashboard 的授權 runtime 收斂成 workspace-aware projection
- 現行資料層與 MCP runtime 已使用 `partner_id` / workspace 邊界運作，而不是一客戶一套獨立 app stack

現在缺的不是再討論一次產品需求，而是補一份明確的部署決策：ZenOS 到底是 shared SaaS、每客戶獨立部署、還是混合模式。這個缺口會直接影響後續的 provisioning、授權、MCP key lifecycle、營運成本與 enterprise 銷售口徑。

## Decision

### D1. 預設架構採 shared runtime + shared database + workspace / partner boundary

ZenOS 的正式多租戶架構定義如下：

- **單一 shared Cloud Run image / service** 承載多個客戶 workspace
- **單一 shared PostgreSQL / Cloud SQL schema** 承載多租戶資料
- **租戶隔離邊界是 workspace / partner scope**，不是 Firebase Project、不是獨立 DB instance
- 所有 MCP / Dashboard read-write 都必須先解析到單一 `active workspace context`，再做 role / visibility / subtree 授權

也就是說，ZenOS 的預設商用型態是 **shared control plane / shared data plane with logical partitioning**，不是 per-tenant full-stack duplication。

### D2. `partner_id` / workspace 是資料邊界；不得再引入第二套 tenant key

資料隔離的正式 key 使用既有 runtime 的 workspace / partner projection：

- DB row 必須屬於單一 workspace boundary
- Query / write path 必須經過 workspace resolution，不得以 client 端傳入 tenant filter 取代
- 新功能若需要 tenant-aware 資料，不得再新增平行的 `tenant_id` / `account_id` 第二套邊界模型，避免與 `SPEC-identity-and-access` 衝突

一句話：**workspace boundary 就是 ZenOS 的 tenant boundary。**

### D3. Firebase 只負責身分與前端資產，不再作為 tenant 隔離單位

Firebase 在多租戶架構中的角色定義為：

- Dashboard authentication / hosting / app integration
- 不是資料隔離單位
- 不是每個客戶各自一個 Firebase Project 的 provisioning 邊界

如果未來某些上層 app 仍需要獨立 Firebase project，那是 app-level integration 決策，不是 ZenOS core tenant model。

### D4. MCP credential 採 per-member identity，不採 per-tenant shared secret

MCP 與 delegated auth 的正式方向是：

- credential 綁 **member / principal**
- runtime 再投影到可用的 `workspace_ids`
- 不使用「整個客戶公司共用一把 tenant key」作為長期正式模型

這與 `ADR-029` 一致：授權邊界在 principal + workspace context，而不是 tenant-wide static credential。

### D5. Dedicated deployment 只作為 enterprise 例外，不是預設路徑

對高資安或合約要求客戶，可支援 dedicated deployment，但定位為 **exception path**：

- 只有明確合約或合規需求時才開 dedicated stack
- dedicated stack 仍應盡量沿用相同的 runtime contract、schema 與 workspace model
- 不得因 dedicated customer 另開一套語意不同的 tenant / permission 模型

也就是說：**shared runtime 是產品預設；dedicated deploy 是商務例外。**

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| 一客戶一 Firebase Project + 一客戶一套 app stack | 物理隔離直觀、好向企業簡報 | 營運成本高、版本推送重、provisioning 慢、與現行 workspace model 脫節 | 與 repo 現況不符，會把現有 shared runtime 推翻 |
| Shared runtime + shared DB + workspace 邏輯隔離 | 與現行 code/spec 一致、營運效率高、版本推送最簡單 | 對授權 runtime、query hygiene、測試矩陣要求更高 | **選這個** |
| Shared runtime + per-tenant DB/schema | 隔離更強 | migration / provisioning / observability 複雜度高，現階段沒有必要 | 現況沒有這層需求，先不增加基礎設施負擔 |
| 每 tenant 一把 shared MCP key | 操作簡單 | 無法追 principal、難做撤銷與審計、與 delegated auth 方向衝突 | 不符合 `ADR-029` 的 credential 模型 |

## Consequences

### Positive

- 部署、升版、修 bug 可對所有租戶一次推送
- 與 `SPEC-identity-and-access` / `ADR-024` / `ADR-029` 對齊，不再同時維護兩套 tenant 敘事
- onboarding 新客戶時，不需要 provisioning 一整套新的 Firebase / app stack
- MCP、Dashboard、workspace sharing 可共用同一套授權與資料邊界

### Negative

- shared runtime 對授權錯誤更敏感；任何 workspace 漏洞都可能變成跨租戶事故
- 測試、migration、資料修復都必須把 workspace boundary 當 P0 邊界處理
- enterprise 客戶若要求 dedicated deployment，營運與 support 成本仍會上升

### Guardrails

- 所有新 API / MCP tool 都必須先解析 `active workspace context`，不得先查資料再過濾
- 預設 fallback 一律回 home workspace，不得保留 shared workspace 特例
- shared runtime 下的 cross-workspace leakage 視為 P0 安全事件

## Implementation

1. 以本 ADR 作為 Multi-Tenant 的正式 deployment SSOT；舊的 `SPEC-multi-tenant` 保留在 archive，視為歷史方案，不再作為現行決策依據。
2. 後續任何提到 tenant / customer isolation 的 spec，必須使用 `workspace boundary` 與 `active workspace context` 語言，不再寫「每客戶一個 Firebase Project」作為預設。
3. 若未來需要 dedicated deployment，另開 implementation spec / ADR，定義 provisioning、升版與營運 contract；但不得改寫本 ADR 的核心 tenant model。
4. 後續 provisioning / billing / admin tooling 任務，預設都以 shared runtime 架構為前提拆解。
