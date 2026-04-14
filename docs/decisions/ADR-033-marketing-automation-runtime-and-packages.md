---
type: ADR
id: ADR-033
status: Draft
ontology_entity: 行銷定位與競爭策略
created: 2026-04-12
updated: 2026-04-14
supersedes: ADR-001-marketing-automation-architecture
---

# ADR-033: Marketing Automation Runtime 與 Skill Packages 決策

## Context

`SPEC-marketing-automation` 已把行銷自動化路徑改為「ZenOS PostgreSQL + MCP + 多人協作」，但現況仍有三個決策缺口：

1. 現有 `ADR-001` 仍是 Firestore + VM crontab + 單人 CLI 假設，和新 spec 方向衝突。
2. Dashboard `/marketing` 目前是 mock data，沒有對應的 API read model。
3. `SPEC-skill-packages` 要求可選 package 安裝，但 `SPEC-zenos-setup-redesign` 仍寫 full-only 安裝。

這個 ADR 的目的，是把「行銷 runtime 路徑」與「skill 安裝策略」統一成單一可實作方案，讓後續 S02~S08 有明確依據。

## Decision

1. **統一為 ZenOS-first Runtime。**  
   行銷資料一律落在既有 ZenOS 模型（L2 module / L3 document / entries / tasks），不再新增 Firestore 路徑。

2. **改為 Dashboard BFF Read Model。**  
   Dashboard 讀取一律經 `GET /api/marketing/projects`（product-grouped）與 `GET /api/marketing/projects/{id}` 聚合 API；前端不得自行拼接多個低階端點。（原 `/api/marketing/campaigns` 在 ADR-035 中改為 `/api/marketing/projects`，此處同步更新。）

3. **選擇 Skill-driven 發佈整合（v1）。**  
   `/marketing-publish` 直接呼叫 Postiz API 並回寫 `job_id/status` 到 post document details；server-side worker 延後到 v1.1。

4. **改為 Package-first 安裝策略。**  
   `skills/release/manifest.json` 新增 `packages[]`，安裝流程支援「必裝基礎治理 + 可選模組包 + 追加安裝」。  
   `SPEC-zenos-setup-redesign` 中 full-only 條款視為舊假設，後續以 `SPEC-skill-packages` 為準更新。

5. **統一採用 Strategy 雙軌承載。**  
   策略全文改存 document；entry 只存 1-200 字摘要與決策重點，避免 entry 長度限制造成資訊折損。

6. **Strategy 欄位擴充（2026-04-14，對齊 SPEC 改版）。**  
   原有 5 欄位（audience/tone/frequency/content_mix/month_goal）擴充為：
   - 必填：audience（string[]）、tone、core_message、platforms（string[]）、frequency（僅長期）、content_mix（僅長期）
   - Optional：campaign_goal（主要短期用）、cta_strategy、reference_materials
   - 長期經營 vs 短期活動的欄位差異由 `project_type` 決定（見 ADR-035）

7. **成效追蹤從 P0 移至 P1（2026-04-14）。**  
   v1 先跑通策略→排程→生成→確認→發佈的主線。Postiz analytics 回收和 metrics sync 延至 P1。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| 延續 ADR-001（Firestore + VM + 單人 CLI） | 已有初步可行性驗證，啟動快 | 與 ZenOS 正規資料層分裂；多人協作與 Dashboard 聚合能力不足 | 不符合 `SPEC-marketing-automation` 的核心方向 |
| 先做 server-side worker，再做 skill | 流程集中在後端，可做強一致排程 | 交付期拉長，基礎設施複雜度高，超出 P0 範圍 | P0 目標是先跑通內容管線，不是先建全自動基礎設施 |
| 維持 setup full-only，不做 package | 相容舊流程，實作成本低 | skill 規模持續膨脹，角色錯配與 context 汙染會惡化 | 不符合 `SPEC-skill-packages` 的 P0 需求 |

## Consequences

- 正面：
  - 行銷資料與 ZenOS 核心治理完全對齊，避免雙資料源漂移。
  - Dashboard 可由穩定 read model 驅動，前端複雜度下降。
  - package 安裝可按角色裁剪，降低無關 skill 干擾。
  - Postiz 先走 skill 路徑可快速驗證 end-to-end。
- 負面：
  - setup/install 與 manifest parser 需要補相容層測試，回歸面增加。
  - skill-side publish 對 operator 操作紀律要求較高，錯誤重試要先靠流程約束。
  - `ADR-001` 需進入 supersede 流程，文件治理工作量增加。
- 後續處理：
  - [未確認] Postiz 部署拓樸（同機/獨立）與 token rotation 責任邊界。
  - [未確認] Review action 的併發衝突策略（最後寫入者 vs optimistic lock）。
  - [已解決] Strategy 欄位定義 → 見上方 Decision #6。
  - [已解決] 成效追蹤優先級 → 降為 P1，見 Decision #7。
  - [新增] 行銷項目資訊架構改為產品分組 → 見 ADR-035。
  - [新增] 文風 Skill 存儲與組合 → 見 ADR-036。

## Implementation

1. 新增 `docs/decisions/ADR-033-marketing-automation-runtime-and-packages.md` 作為本輪決策基準。
2. 依 `TD-marketing-automation-implementation` 實作 `src/zenos/interface/marketing_dashboard_api.py` 端點（projects list/detail + post review + strategy + styles）。API 路徑以 ADR-035 的 `/api/marketing/projects` 為準。
3. 將 `dashboard/src/app/marketing/page.tsx` 從 mock 常數改為呼叫 marketing API client。
4. 在 `skills/release/workflows/` 新增 5 個 marketing workflow skills，全部走既有 MCP tools。
5. 擴充 `skills/release/manifest.json`、`setup_content.py`、`setup_adapters.py`、`skills_installer.py` 以支援 `packages[]`。
6. 完成 S07 時，將 `ADR-001` 標記為 superseded，並在 spec/plan 補上 supersede 關聯。
