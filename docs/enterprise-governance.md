# 企業導入治理：部門架構與責任歸屬

> 這份文件記錄的是 ZenOS 實際導入企業時會碰到的治理問題——特別是「這份文件誰負責？」這類傳統管理問題。
> 這跟 ZenOS 的終極目標（AI agents 共享 context）有一點偏離，但在向客戶 propose 時幾乎一定會被問到。
>
> 定位：**Proposal 武器庫** — 不影響核心架構，但影響客戶是否買單。

---

## 問題：傳統部門架構 vs ZenOS 的 Who 維度

傳統企業對每份文件有一條明確的責任鏈：

```
撰寫人 → 部門主管 → 負責部門 → 最終核准人
```

這條鏈解決的是**治理問責**：出了問題找誰。

ZenOS 的 Who 維度解決的是另一件事——**context 分發**：這份知識跟哪些角色有關。

兩者本質上不同：

| 面向 | 傳統部門治理 | ZenOS Who 維度 |
|------|------------|---------------|
| 回答的問題 | 「這份文件誰負責？」 | 「這份知識跟誰有關？」 |
| 值的數量 | 單一（一個負責人/部門） | 多值（可能跟行銷、產品、客服都有關） |
| 用途 | 問責、簽核、稽核 | Context 過濾——決定哪個角色的 AI agent 能看到 |
| 變動頻率 | 低（組織調整才變） | 中（隨文件內容演變） |
| 關注的對象 | 人 / 部門 | 角色（角色穩定，人流動） |

**核心洞察：Who 和 Owner 是兩個不同的問題，不能用同一個欄位。**

---

## 解法：Who + Owner 分離

### Who（多值）— context 分發

Who 回答的是：「這份知識跟哪些角色有關？」

```yaml
# 一份產品規格文件的 Who 標籤
who:
  - product        # 產品團隊要讀（這是他們寫的）
  - engineering    # 工程團隊要讀（要照這個做）
  - marketing      # 行銷團隊要讀（要用這個寫文案）
  - support        # 客服團隊要讀（客戶問到要能答）
```

Who 是 ZenOS 核心架構裡四維標籤的一部分。它直接決定 AI agent 的 context 範圍：行銷的 agent 問問題時，Who 包含 `marketing` 的 entry 會被納入 context。

### Owner（單值）— 治理問責

Owner 回答的是：「這份知識的 ontology entry 由誰負責確認？」

```yaml
# 同一份產品規格文件的 Owner
owner:
  role: product           # 產品團隊負責
  confirmedBy: "barry"    # 具體確認人
  confirmedAt: "2026-03-15"
```

Owner 對應的是 ZenOS 已有的 `confirmedByUser` 機制：

- AI 自動產生/更新 ontology entry → draft 狀態
- Owner 確認 → 正式生效
- 如果 Owner 沒確認，entry 仍然可用（帶 draft 標記），但 AI agent 在使用時會知道「這是未確認的」

### 兩者的互動

```
文件 CRUD 事件
    ↓
AI 自動更新 ontology entry（包括 Who 標籤）
    ↓
通知 Owner 確認
    ↓
Owner confirmedByUser → entry 正式化
    ↓
所有 Who 角色的 AI agent 收到更新後的 context
```

Who 決定「誰的 agent 能看到」，Owner 決定「誰要為正確性負責」。兩者獨立運作。

---

## 不同公司規模的 Owner 映射

### 2-5 人的微型公司（ZenOS Phase 0 目標客群）

```
現實：老闆 = 所有文件的 Owner
      （或者根本沒有明確的 Owner）

ZenOS 做法：
  - 預設 Owner = 建立 ontology entry 時觸發的人
  - 大部分情況 Owner 就是老闆
  - 不需要複雜的 Owner 指派流程
  - confirmedByUser 的確認佇列 = 老闆的 to-do list
```

這個階段 Owner 幾乎不是問題——公司小到一個人就能確認所有東西。

### 10-30 人的小型公司

```
現實：開始有部門分工
      行銷的文件行銷負責、產品的文件產品負責

ZenOS 做法：
  - Owner 預設 = 文件所在位置的推斷
    （marketing/ 資料夾下的文件 → Owner: marketing_lead）
  - AI 可以從 git commit author / Google Drive owner 推斷
  - 推斷結果走 confirmedByUser → 老闆或部門負責人確認
  - 一旦確認，未來該領域的新文件自動指派相同 Owner
```

### 50-200 人的中型公司

```
現實：有正式的部門架構和簽核流程
      客戶 propose 時最常問的就是這種規模

ZenOS 做法：
  - 支援 Owner 繼承規則：
    部門 → 子團隊 → 具體負責人
  - 整合既有的組織結構（從 Google Workspace / MS Teams 讀取）
  - Owner 變更走確認流程（不是 AI 自動決定）
  - 可以設定「代理確認人」——Owner 不在時由誰確認
```

---

## Proposal 問答：客戶會怎麼問

### Q1：「這份文件的負責人是誰？出了問題找誰？」

> ZenOS 用 Owner 欄位追蹤每份知識的治理負責人。Owner 是單一角色（不是多人），負責確認 ontology entry 的正確性。AI 自動推斷 Owner，人確認。
>
> 但要注意：ZenOS 的 Owner 管的是「ontology entry 的正確性」，不是「原始文件的業務責任」。原始文件的簽核/負責人仍在原本的系統裡（Google Drive 的 owner、Notion 的 page owner）。ZenOS 不取代那些。

### Q2：「我們有部門分工，行銷部的東西工程部不能亂改。」

> ZenOS 的 Who 標籤決定 context 可見性：行銷的 agent 能看到行銷相關的 context，但**看到 ≠ 能改**。
>
> Ontology entry 只能透過 ZenOS Governance Service 修改（MCP 的 `propose_update` → 進入確認佇列 → Owner 確認）。任何 agent 都不能直接改 ontology——只能「建議修改」。
>
> 所以部門隔離在 ZenOS 裡有兩道關卡：
> 1. Who 決定能不能看到
> 2. Owner + confirmedByUser 決定能不能生效

### Q3：「我們有正式的簽核流程，ZenOS 怎麼配合？」

> ZenOS 不取代簽核流程。原始文件的簽核仍在原本的系統裡。
>
> ZenOS 的 confirmedByUser 是 ontology 層的確認——確認的是「AI 對這份文件的語意描述是否正確」，不是確認「這份文件本身的業務內容」。
>
> 兩者可以平行運作：
> - 公司原有系統：文件簽核（業務層）
> - ZenOS：ontology 確認（context 層）
>
> 如果公司希望兩者連動（文件簽核完 → 自動觸發 ontology 確認），可以在 Phase 2 的 Adapter 層加入 webhook 整合。

### Q4：「人離職了怎麼辦？」

> ZenOS 的 Who 維度存角色不存人。「行銷」是角色，不是「小美」。小美離職，ontology 不用改——只改 role mapping（誰是行銷角色）。
>
> Owner 欄位也是角色優先：Owner: marketing_lead，不是 Owner: xiaomei。具體的 confirmedBy 人名只是記錄「最後一次誰確認的」，不是綁定。

### Q5：「多個部門都覺得自己該負責同一份文件怎麼辦？」

> Who 是多值的：這份文件可以跟行銷、產品、工程都有關。但 Owner 是單值的：只有一個角色負責 ontology entry 的正確性。
>
> 當多個部門爭 ownership 時，其實爭的是「誰對原始文件有業務責任」——這不是 ZenOS 要解決的問題。ZenOS 只需要一個 Owner 來確認 ontology entry。
>
> 如果真的有爭議，建議用 confirmedByUser 的機制讓多方依序確認（多重確認模式，Phase 2 可支援）。

---

## Who 的三層消費模型

### 問題：角色是「員工」還是「agent」？

不同公司處於 AI 採用光譜的不同位置：

```
無 Agent ←————————————→ Agent-Native
傳統 SMB          混合型           AI-driven
角色=員工      角色=員工+工具      角色=員工+獨立Agent
```

Who 的設計必須在整個光譜上都能運作，且不能因為公司治理模式不同而需要不同 schema。

### 解法：三層分離

```
Ontology 層（ZenOS 管）
┌─────────────────────────────────┐
│  Who: [marketing, product, ...] │  ← 純職能角色
└─────────────────────────────────┘
              │
公司層（老闆/主管設定，全公司可見）
┌─────────────────────────────────┐
│  marketing → Barry, 小美         │  ← 角色→員工
└─────────────────────────────────┘
              │
個人層（員工自己設定，只有自己看得到）
┌─────────────────────────────────┐
│  Barry → agent-1, agent-2, ...  │  ← 員工→agents
└─────────────────────────────────┘
```

| 層 | 誰設定 | 誰看得到 | 變動頻率 | ZenOS 管不管 |
|----|--------|---------|---------|------------|
| 職能角色 | ZenOS AI + 人確認 | 全公司 | 低 | ✅ 管 |
| 角色→員工 | 老闆/主管 | 全公司 | 中 | ✅ 管（Phase 1+ Dashboard） |
| 員工→agents | 員工自己 | 只有自己 | 高 | ❌ 不管 |

**第三層為什麼不管：** Agent 本質是 skill，員工隨時可能新增、修改、停用。靜態綁定的維護成本隨 agent 數量線性增長。而且公司派工到「Barry」就結束了——Barry 底下開了 5 個 agent 還是自己手做，是他的事。

### Pull Model：Agent 自宣告身份

不是 ZenOS 把 context 推給 agent，而是 agent 來的時候自己說「我是 marketing」，然後拉走需要的 context。

```
傳統思路（Push / 綁定）：
  ZenOS 維護一張表：marketing → [agent-1, agent-2, 小明]
  agent-3 出現了 → 要有人去更新這張表
  ❌ 維護成本隨 agent 數量線性增長

正確思路（Pull / 自宣告）：
  每個 agent 的 skill 定義裡寫著：我的職能是 marketing
  agent 透過 MCP 讀 ontology 時，自帶 role filter
  ✅ 新增 agent = 新增 skill，零綁定成本
```

### Agent 身份宣告指引（用戶端設定）

ZenOS 不參與員工底下 agents 的關係管理，但提供指引讓用戶方便設定 agent 身份。

**方式一：在 Skill / System Prompt 中宣告（推薦）**

```markdown
# Social Media Agent

你是負責社群媒體的 agent。
你的職能角色：marketing

## ZenOS Context 設定
讀取 ontology 時使用以下過濾：
- who: marketing
- 額外關注：brand, content
```

Agent 透過 MCP 呼叫 ZenOS 時帶入角色：
```
query_ontology(who: "marketing")
→ 回傳所有 Who 包含 marketing 的 entry
```

**方式二：在用戶環境設定檔中集中管理（進階）**

```yaml
# ~/.zenos/agent-routing.yaml（存在員工本地環境）
# 這個檔案只有員工自己看得到，ZenOS 不讀取也不管理

my_agents:
  copywriter-agent:
    roles: [marketing]
    focus: [brand, content]  # 可選：進一步縮小 context 範圍

  analytics-agent:
    roles: [marketing, product]
    focus: [metrics, campaign-performance]

  social-agent:
    roles: [marketing]
    focus: [social-media, community]
```

**方式三：不設定（傳統員工）**

沒有 agent 的員工直接透過 Dashboard 或 MCP 讀 ontology，以自己被指派的角色過濾。第三層不存在，零設定成本。

### 演化路徑

同一間公司從「無 agent」演化到「agent-native」時，ontology 零改動——只改第二層（公司 Dashboard）和第三層（員工本地設定）：

```
Phase 0（無 agent）：  Who = 角色 → 人直接讀
Phase 1（開始用 agent）：Who = 角色 → 人讀 + 工具型 agent 讀
Phase 2（agent-native）：Who = 角色 → 人偶爾讀 + 多個獨立 agent 各自讀
```

---

## 設計原則

1. **ZenOS 不取代原有的組織治理** — Owner 只管 ontology entry 的正確性，不管原始文件的業務簽核
2. **角色優先，個人其次** — Who 和 Owner 都以角色為單位，人員異動不影響 ontology
3. **AI 推斷 + 人確認** — Owner 指派走 confirmedByUser，跟 ontology 其他欄位一致
4. **Phase 0 不用管** — 微型公司 Owner ≈ 老闆，不需要複雜的 ownership 機制
5. **漸進式複雜度** — 公司長大了再加 Owner 繼承規則，不預先過度設計

---

## 與核心架構的關係

這些機制不改變 ZenOS 的核心設計（四維標籤 + 雙層治理 + MCP + Firestore）。它們是在既有的 `confirmedByUser` 機制上的**延伸**：

```
Phase 0：   confirmedByUser = 老闆確認一切
Phase 1：   confirmedByUser + Owner 角色指派
Phase 2：   confirmedByUser + Owner 繼承規則 + 多重確認 + Adapter 整合
```

每個 Phase 都向後相容。Phase 0 的 ontology entry 到 Phase 2 仍然有效。

---

## 構想：Cryptographic Governance Trail（區塊鏈 × 責任鏈）

> 定位：發散式構想，增強 promotion power。不影響核心架構，不在 Phase 0-1 實作。

### 動機

confirmedByUser 的治理紀錄存在 Firestore——但 Firestore 是 ZenOS 控制的。高資安需求的客戶（會計事務所、法律事務所、醫療診所）會問：「怎麼證明你沒有竄改紀錄？ZenOS 倒了怎麼辦？」

公司規模小不代表安全需求低。這些行業人少但資料敏感度極高。

### 三層設計

**Layer 1：Hash Chain（Phase 1 即可內建，零成本）**

每次 confirmedByUser 事件產生一筆紀錄，形成鏈：

```
{
  entryId, action, confirmedBy, timestamp,
  contentHash,          // ontology entry 內容的 SHA-256
  previousEventHash     // 前一筆事件的 hash → 形成不可竄改的鏈
}
```

存在 Firestore 裡。不需要任何區塊鏈基礎設施。任何人事後想竄改歷史紀錄，hash 斷裂即可偵測。

Promotion 語言：「cryptographic governance trail」「密碼學等級的治理軌跡」。

**Layer 2：Periodic Anchor to Public Chain（Phase 2 選配）**

每日/每週將 hash chain 的 Merkle root 寫入公鏈（Ethereum L2 如 Base / Arbitrum），一筆交易 < $0.01。

效果：驗證能力不依賴 ZenOS 存活。任何人拿著 hash chain + 公鏈上的 Merkle root，可以獨立驗證整條治理歷史。

**Layer 3：Full On-Chain（特殊客戶）**

每筆 confirmedByUser 事件直接上 L2 公鏈。適用於法規要求不可竄改紀錄的行業（醫療、金融、法律）。成本仍極低（L2 每筆 < $0.01），但需要客戶理解區塊鏈。

### Proposal 加分點

| 客戶類型 | 適用層級 | Pitch |
|---------|---------|-------|
| 一般 SMB | Layer 1 | 「你的知識治理有完整的密碼學驗證軌跡」 |
| 高資安 SMB（會計/法律/醫療） | Layer 2 | 「治理紀錄每天 anchor 到公鏈，ZenOS 倒了也能驗證」 |
| 合規需求（ISO 27001 / SOC 2） | Layer 2-3 | 「稽核時直接出示鏈上紀錄，零爭議」 |

### 不做什麼

- 不做 token / NFT / 任何 crypto 金融產品
- 不要求客戶有錢包或理解區塊鏈
- 不把 ontology 內容上鏈——只上 hash（隱私）
- Layer 2-3 永遠是選配，不影響核心功能

---

## Changelog

- 2026-03-21：初版。從 spec.md 的 Who 維度和 confirmedByUser 機制延伸，記錄企業導入時的部門治理問題和 Proposal 問答。
- 2026-03-21：新增 Cryptographic Governance Trail 構想（三層設計：Hash Chain → Periodic Anchor → Full On-Chain）。
