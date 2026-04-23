---
type: ADR
id: ADR-025-zenos-core-layering
status: Superseded
ontology_entity: zenos-core
created: 2026-04-09
updated: 2026-04-23
superseded_by: ADR-048-grand-ontology-refactor
supersede_reason: Core 分層決策（Knowledge / Action / Document Layer 分治）已由 Grand Refactor 收斂為 L3-Action + L3-Document subclass 併入 Knowledge Layer；新 canonical 在 SPEC-zenos-core v2 + 主 SPEC v2 §3
---

# ADR-025: ZenOS Core 分層邊界

> **2026-04-23 Supersede note**：本 ADR 的三層分治決策於 Grand Refactor 收斂——Action Layer 與 Document Layer 併入 Knowledge Layer 成 L3-Action / L3-Semantic subclass。Canonical 現在見 `SPEC-zenos-core` 與主 SPEC v2 §3。

## Context

ZenOS 定位為中小企業的 AI Context 層——一次建 ontology，所有 AI agent 共享同一套 context。隨著產品從單一 ontology 工具演化為多 application 平台（CRM、Access Management、未來 vertical apps），需要一條清晰的線把「平台核心」與「應用層」切開。

`SPEC-zenos-core` 已定義五層分離模型，但以下架構選擇尚未有正式 ADR 鎖定：

1. 為什麼是五層而不是三層或四層？
2. Subtask 為什麼排除在 Core 外？
3. Plan 的最小職責邊界在哪？
4. Task 為什麼不是 entity？
5. Application Layer 如何映射到 Core？

這些決策會約束所有後續 spec 與 application module 的架構方向。做錯了修正成本極高——每個下游 spec（ontology、task governance、identity & access、agent integration、document bundle）都引用 Core 分層作為上位約束。

## Decision Drivers

- ZenOS 是 platform layer，不是單一 application；Core 必須穩定到讓多個 app 安全共享
- 中小企業導入成本必須低；分層過多會增加理解成本與開發成本
- 既有 spec 已經按五層組織（SPEC-ontology-architecture、SPEC-task-governance、SPEC-identity-and-access、SPEC-agent-integration-contract、SPEC-document-bundle），改動分層等於回退所有下游 spec
- 每一層必須有明確的「只有放在 Core 才能解決」的理由，否則應留在 Application Layer

## Decision

### D1. 採用五層 Core 模型，不採三層或四層

ZenOS Core 由以下五層組成：

| 層 | 職責 | 對應 Spec |
|---|---|---|
| **Knowledge Layer** | L1-L3 entity、relationship、entries、document proxy、source governance | SPEC-ontology-architecture |
| **Action Layer** | Task、Plan、lifecycle、review/confirm、task-to-ontology linkage | SPEC-task-governance |
| **Identity & Access Layer** | User、workspace、active workspace context、visibility、subtree authorization | SPEC-identity-and-access |
| **Agent Runtime Layer** | MCP tools、workspace-aware context delivery、capture/sync/analyze/confirm 治理入口 | SPEC-agent-integration-contract |
| **Document Platform Contract** | doc entity single/index 語意、per-source schema、source platform 抽象、rollout contract | SPEC-document-bundle |

**考慮過的替代方案：**

**替代方案 A：三層模型（Knowledge + Action + Access）。** 把 Agent Runtime 視為 Action Layer 的子集，把 Document Platform Contract 視為 Knowledge Layer 的子集。問題：Agent Runtime 不只服務 Action Layer——它同時提供 knowledge read、document read、governance analyze，橫跨多層。Document Platform Contract 定義的 source adapter、rollout boundary、platform URI validation 是獨立於 entity 語意的基礎設施問題。三層模型會讓這兩個關注點被迫塞進不屬於它們的層。

**替代方案 B：四層模型（Knowledge + Action + Access + Agent Runtime，Document 併入 Knowledge）。** 問題：L3 document entity 的語意索引模型（single/index、multi-source、source platform contract）複雜度已足夠獨立。ADR-022 證明 document bundle 的資料模型、mutation 語意、rollout 策略需要獨立決策空間。併入 Knowledge Layer 會讓該層變得過於龐大，且 Document Platform Contract 的 rollout 節奏（github 先、gdrive 後、notion 更後）與 Knowledge Layer 的穩定性要求衝突。

**選擇五層的理由：**

1. 每一層有獨立的演化節奏——Knowledge 最穩定，Document Platform Contract 按平台 rollout，Agent Runtime 隨 MCP 生態演進
2. 每一層有獨立的 spec owner 和決策邊界，避免單一 spec 過度膨脹
3. 五層與既有 spec 結構一對一對應，不需要回退任何下游文件
4. 每一層都能回答「為什麼不能放在 Application Layer」——Knowledge 是共享語意骨架、Action 是跨 app 的可驗收工作單位、Access 是共享授權邊界、Agent Runtime 是跨廠牌的 MCP contract、Document Platform Contract 是跨平台的文件治理基礎設施

**Tradeoff：** 五層比三層多了理解成本。對一個只有 2-5 人的中小企業團隊來說，五層看起來「很重」。緩解方式：Application Layer 開發者只需要知道「Core 提供哪些 contract 可以用」，不需要理解五層的內部結構。五層是給 platform 開發者（我們自己）的約束，不是給 app 開發者的負擔。

### D2. Subtask 排除在 Core 外

**決策：** app-specific subtask / checklist / execution step 留在 Application Layer。若某 subtask 需要獨立指派、獨立驗收、或獨立知識回饋，必須升格為 Core Task。

**理由：**

Core Task 的語意是「最小可指派、可驗收、可回饋知識的工作單位」。這五個條件（單一 outcome、可指派、可驗收、可連回 knowledge、可留下 result）是 Core 提供跨 app 治理的基礎。Subtask / checklist 不滿足這些條件——它們通常是 app-specific 的執行步驟，沒有獨立的 outcome 和驗收邊界。

**考慮過的替代方案：**

**替代方案：Core 定義通用 subtask schema。** 問題：不同 app 的 subtask 語意差異極大——CRM 的 follow-up checklist、Zentropy 的 daily execution step、PM tool 的 sprint sub-item 沒有共同的語意基礎。強行抽象會讓 Core 的 subtask schema 變成「什麼都能塞但什麼都不精確」的垃圾桶，最終 app 還是得自己維護真正的執行模型。

**Tradeoff：** Application Layer 需要自己管理 subtask → app 間的 subtask 不可互通。這是刻意的——互通的代價是 Core 被 checklist 污染，比 app 各自管理的代價更高。

**升格規則：** 當某個 subtask 開始需要跨人協作、授權控管、或知識回饋時，它已經不是 subtask 了——應升格為 Core Task。這個判斷由 app 自行負責，Core 不做自動偵測。

### D3. Plan 是最小 orchestration primitive，不承擔 PM methodology

**決策：** Plan 在 Core 只負責四件事：grouping（綁 tasks）、sequencing（定義順序與依賴）、ownership（責任人）、completion boundary（entry/exit criteria）。Plan 不承擔 milestone、sprint、phase 等 PM methodology 概念。

**理由：**

不同 application 採用不同的 PM 方法論——Zentropy 用 milestone-based delivery、某些團隊用 sprint、某些用 kanban。如果 Plan 在 Core 層就承擔 sprint / milestone 語意，等於強制所有 app 採同一種 PM 框架。

**考慮過的替代方案：**

**替代方案 A：Plan 定義可擴展的 plan_type enum（sprint / milestone / kanban_cycle）。** 問題：enum 一旦進入 Core，每新增一種 PM 方法論就要改 Core schema。Core 的改動影響所有 app——這是不成比例的耦合。

**替代方案 B：不要 Plan，只用 Task 的 depends_on 自組織。** 問題：沒有 grouping 就無法定義「這批 tasks 的共同交付目標是什麼」和「什麼條件算完成」。depends_on 只解決順序問題，不解決邊界問題。

**選擇最小 Plan 的理由：** Plan 提供的四個能力（grouping + sequencing + ownership + completion boundary）是所有 PM 方法論的公因數。Application Layer 可以自由把 Plan 映射成 sprint、milestone、或任何它需要的概念——映射邏輯在 app，不在 Core。

**Tradeoff：** Plan 在 Core 層「太薄」——app 需要自行建立 Plan → app-specific concept 的映射。這增加了 app 開發成本，但保護了 Core 的穩定性。

### D4. Task 不是 entity，是 Action Layer primitive

**決策：** Task 屬於 Action Layer，不屬於 Knowledge Layer。Task 不是 entity，不出現在 ontology schema 中，不適用 entity 的分層模型（L1/L2/L3）。Task 透過 `linked_entities` 連回 ontology，是 ontology 的消費者，不是 ontology 的一部分。

**理由：**

Entity 的判斷標準（見 SPEC-ontology-architecture）：

1. 跨專案/跨時間存活嗎？Task 不會——做完就結束
2. 有 What/Why/How/Who 四維可描述嗎？Task 描述的是「要做什麼」，不是「這個概念是什麼」
3. 能成為其他知識的錨點嗎？Task 不能——它是行動，不是知識

Task 有自己的生命週期（todo → in_progress → review → done）、指派人、驗收條件——這些是 action 語意，不是 knowledge 語意。如果把 Task 視為 entity，知識地圖會被「修復 bug #123」「寫測試」之類的短命節點淹沒，失去「公司長期知識骨架」的定位。

**考慮過的替代方案：**

**替代方案：Task 作為一種 L3 entity（如 project、goal、role）。** 問題：L3 entity 共享同一套 visibility、sharing、governance 規則。但 Task 的授權模型（assignee-based）和 L3 entity 的授權模型（subtree-based）根本不同。強行統一會讓兩套模型都變得不自然。

**Tradeoff：** Task 與 entity 是兩套獨立的 schema → 需要 `linked_entities` 做橋接 → 橋接品質依賴 agent 和 server 的 enrichment。這比把 Task 塞進 entity 的代價更低——橋接可以漸進改善，但模型污染一旦發生就很難還原。

### D5. Application Mapping Contract：app 如何映射到 Core

**決策：** Application Layer 必須遵守以下映射規則：

1. **App milestone / phase → Core Plan。** App 可以定義自己的 milestone 概念，但如果需要跨人協作和驗收追蹤，必須映射到一個或多個 Core Plan。
2. **App task（需跨人協作 + 授權 + 驗收 + 知識回饋）→ Core Task。** 這是強制映射——任何滿足這四個條件的工作單位必須在 Core 有對應 Task。
3. **App subtask / checklist / internal step → 留在 App。** 不需要上述四個條件的執行步驟，不得強制寫入 Core。
4. **App 不得以 subtask 取代 Core Task 的驗收邊界。** 如果一個工作需要 Core 級別的驗收（review + confirm），就必須是 Core Task，不能用 app subtask 做偽驗收。
5. **App entity → Core L1/L2/L3。** App 可以把自己的核心協作主軸橋接為 Core L1，只要該節點承擔的是可被獨立授權與分享的 subtree root。以 CRM 為例，`company` 在「一個客戶就是一個獨立共享邊界」的場景下可橋接為 L1；`contact` 則應作為其下游 knowledge node，而不是另一個平行 L1。App 可以增加 Core 沒有的 domain object（如 CRM 的 Deal），但不得反向改寫 Core 的 entity 語意。
6. **App surface → 不自動共享。** App module 預設只存在於自己的 workspace surface。跨 workspace 共享必須由各 app spec 明確定義 contract，不得默認沿用 Core 的共享規則。

**CRM 作為映射範例：**

| CRM 概念 | Core 映射 | 說明 |
|---|---|---|
| 公司（Company） | L1 entity (type: company) | 在客戶本身就是共享邊界時，作為一棵可分享 subtree 的 root；CRM schema 獨立 |
| 聯絡人（Contact） | 下掛於 Company L1 的 entity (type: person) | 關聯到公司 entity，不作為平行 L1 |
| 商機（Deal） | CRM 自有 | 不橋接為 entity 或 task（Phase 0） |
| 活動紀錄（Activity） | CRM 自有 | app-specific，不進 Core |
| CRM Dashboard | CRM 自有 surface | 不跨 workspace 共享 |

**理由：** 映射規則的核心目的是防止 Application Layer 反向污染 Core。CRM 的 Deal pipeline、activity log、kanban UX 是 app-specific 的——它們對 Core 的 ontology、task lifecycle、access model 沒有貢獻。但 CRM 的公司和聯絡人是「公司知識骨架」的一部分，應該進入 Core 被所有 app 共享。

## Consequences

### Positive

- **每一層有獨立的 spec owner**，避免單一 spec 膨脹到無法維護。目前五份 spec 各自可管理、可審查、可獨立演進。
- **Application Layer 有明確的「可以做」與「不可以做」清單**，新 app module 開發時不需要猜測邊界。
- **Task 與 entity 的清晰分離**，保護知識地圖不被短命的 action 節點淹沒。
- **Subtask 排除在 Core 外**，保護 Core 的 action model 不被 app-specific checklist 污染。
- **Plan 的最小職責**，讓不同 PM 方法論可以共存。

### Negative

- **五層模型的學習曲線**比三層高。新的 platform contributor 需要理解五層的邊界和互動方式。
- **Subtask 不在 Core → app 間 subtask 不互通**。如果未來有「跨 app 的 checklist 共享」需求，需要回來重新評估。
- **Plan 太薄 → app 需要自建映射**。每個 app 都需要寫「我的 milestone 怎麼對應到 Core Plan」的邏輯。
- **Application Mapping Contract 是軟約束**。沒有 runtime enforcement，靠 spec review 和 code review 維護。

### Risks

- **最大風險：Document Platform Contract 獨立成層是否過早。** 目前只有 github reader 落地，gdrive/notion/wiki 都還沒有。如果平台擴展速度比預期慢，這一層可能長期只服務 github 一種場景。**緩解：** 即使只有 github，multi-source 模型（ADR-022）和 source platform abstraction 已經在用。獨立成層的成本是多了一份 spec，但不會增加 runtime 複雜度。
- **中等風險：Application Mapping Contract 缺乏 runtime enforcement。** App 可能違反規則（例如繞過 Core Task 做偽驗收），直到 code review 才被發現。**緩解：** Phase 0 只有我們自己開發 app，靠 spec review 足夠。未來開放第三方 app 時需要加 runtime validation。
- **低風險：五層模型可能被誤解為五個 microservice。** 五層是概念分層，不是部署分層。所有層共享同一個 Python backend 和同一個 PostgreSQL database。**緩解：** 在本 ADR 明確聲明。

## Implementation Impact

本 ADR 是「鎖定方向」的決策，不直接產生新 code。但對既有 codebase 和 spec 有以下約束：

### 對既有 Spec 的影響

| Spec | 影響 | 行動 |
|---|---|---|
| SPEC-zenos-core | 本 ADR 的源頭 spec，無衝突 | 無需修改 |
| SPEC-ontology-architecture | 已正確標註 layering note：Knowledge Layer only，Task 不是 entity | 無需修改 |
| SPEC-task-governance | 已正確標註 layering note：Action Layer only | 無需修改 |
| SPEC-identity-and-access | 已正確標註 layering note：Identity & Access Layer。2.1 節已更新為多身份來源模型（Firebase Auth + identity_link + API key），反映 ADR-029 的 federation 設計 | 2026-04-10 已更新 §2.1 |
| SPEC-agent-integration-contract | 已定義三層責任分工（MCP / Server / Skill），與 Agent Runtime Layer 一致 | 無需修改 |
| SPEC-document-bundle | 已標註為 doc entity SSOT，與 Document Platform Contract 一致 | 無需修改 |
| SPEC-crm-core | 已標註為 Application Layer module，已定義 L1 橋接規則 | 無需修改 |

### 對既有 Code 的影響

- `src/zenos/` 的 DDD 四層（domain / application / infrastructure / interface）是部署架構，與本 ADR 的五層概念分層是正交關係。不需要因為概念五層而改動 code 的目錄結構。
- 後續新增 app module（如 CRM）時，必須遵循 D5 的映射規則。CRM schema 已採獨立 PostgreSQL schema（`crm`），符合 Application Layer 不混用 Core schema 的原則。

### 對未來 Spec 的約束

所有新增 spec 若涉及 entity / knowledge / document / task / plan / workspace / access / app workflow，必須在開頭聲明自己位於哪一層。無法判定層級時，必須先回到 SPEC-zenos-core 做邊界澄清。

## Clarification

五層是概念分層（concern separation），不是部署分層（deployment boundary）。所有五層共享：

- 同一個 Python backend（`src/zenos/`）
- 同一個 PostgreSQL database（`zenos` schema）
- 同一個 MCP server（`src/zenos/interface/tools.py`）
- 同一個 Cloud Run instance

概念分層約束的是「哪個 spec 負責哪個決策」和「哪些語意可以被 application layer 改寫」，不是「部署時要拆成幾個 service」。
