# SPEC: 公司內部資料權限控管（Intra-Company Data Permission）

> PM: Claude (PM role) | Date: 2026-03-25 | Status: Draft

## 問題

ZenOS 的核心價值是「全公司同一套 context」，但**全公司看到同一套 context ≠ 全公司看到所有東西**。

現在 ZenOS 的權限模型只有認證（你是不是這家公司的人）和粗粒度角色（admin/member），沒有任何資料層級的存取控制。結果：

1. **老闆的薪資系統 entity 被行銷 agent 讀到** → 行銷 agent 寫出的內容可能洩漏薪資結構
2. **財務相關的 blindspot 被所有人看到** → 新人 agent 搜 ontology 時看到「財務報表與實際不符」的盲點
3. **人事評估文件被全公司 agent 引用** → AI 回答問題時引用了不該出現的績效評語
4. **客戶合約細節被競品分析 agent 讀到** → agent 可能在對外溝通中透露合約金額

**ontology 越完整，這個問題越嚴重。** 因為 ZenOS 的目標是讓 AI agent「懂你的公司」——但懂得太多又沒有邊界，就是資安事故的溫床。

### 為什麼這僅次於 ontology 重要

Ontology 是知識結構。權限是知識邊界。

沒有 ontology → AI 不懂公司 → 沒有價值。
有 ontology 但沒有權限 → AI 知道太多 → 不敢用。

中小企業的老闆通常是數據擁有者本人，他對風險的感知是直覺的。如果他覺得「把公司知識交給 AI 太危險」，他連 ontology 都不會建。**權限是 ontology 被採納的前提。**

---

## 目標用戶

| 用戶 | 需求 |
|------|------|
| 老闆（admin） | 控制「誰的 agent 能看到什麼」，特別是敏感資訊（財務、人事、合約） |
| 部門主管 | 確保部門 agent 只看到該看的，不被其他部門的雜訊干擾 |
| 一般員工 | 不需關心權限設定，但 agent 自動只看到自己該看的 |
| AI Agent | 查 ontology 時只拿到授權範圍的結果，不需要自己判斷什麼能用什麼不能用 |

---

## 設計原則

### 1. 權限在 server 端強制，不靠 agent 自律

Agent 不會自我審查。如果 search 結果包含敏感 entity，agent 就會用。**過濾必須在 ZenOS server 端完成，MCP response 只回傳授權範圍內的資料。**

### 2. 預設開放，標記敏感

中小企業不會為每個 entity 設權限。預設 `visibility: "public"`，只有被明確標記為 `restricted` 或 `confidential` 的 entity 才會被過濾。**少量標記 > 大量設定。**

### 3. 角色驅動，不做 per-entity ACL

中小企業沒有 IT 部門維護複雜的 ACL。權限跟著「職能角色」走（ontology 的 Who 維度），不是跟著個別 entity 設定。**老闆設定「行銷能看什麼角色的東西」，不是「行銷能看 entity-123」。**

### 4. 繼承式傳播

L1 product 設為 `restricted` → 底下的 L2、L3、相關 documents、tasks 都自動 restricted。不需要逐個設定。

### 5. 與漸進式信任一致

ZenOS 的核心是漸進式信任（spec Part 5）。權限模型也要漸進：
- 剛開始不設任何權限 → 全公司 agent 看到所有東西 → 這是刻意的，因為初期需要最大覆蓋率
- 隨著 ontology 成熟，老闆開始標記敏感 entity → 逐步收緊
- 不需要一開始就設好所有權限 → 這符合 SMB 的使用習慣

---

## 權限模型設計

### 三個維度

```
誰（Who）         × 看什麼（What）      × 能做什麼（Action）
職能角色/個人       entity scope         read / write / admin
```

### Who：誰在存取

| 身份 | 說明 | 解析方式 |
|------|------|---------|
| admin | 公司管理員 | partner.isAdmin = true |
| member:{role} | 特定職能角色的成員 | partner 綁定的職能角色（如 marketing, engineering） |
| member | 一般成員（無特定角色） | partner.isAdmin = false |
| agent:{owner} | 某個成員的 AI agent | MCP API key → partner → 繼承 partner 的權限 |

**關鍵：Agent 的權限 = Owner（成員）的權限。** Agent 不是獨立的權限主體。Barry 的 agent 能看到的 = Barry 能看到的。

### What：能看到哪些資料

#### Entity Visibility（三級）

| visibility | 誰能看 | 使用場景 |
|---|---|---|
| `public` | 所有成員和 agent | 預設值，大部分 entity |
| `role-restricted` | 指定職能角色 + admin | 部門專屬知識（如：工程架構只有 engineering 角色能看） |
| `confidential` | 僅 admin + 明確授權的個人 | 薪資、合約、人事評估 |

#### Entity Scope 欄位

```
entities/{id}
  visibility: "public" | "role-restricted" | "confidential"
  visible_to_roles: ["marketing", "product"]   // visibility=role-restricted 時生效
  visible_to_members: ["partner-id-123"]        // visibility=confidential 時的額外授權
```

#### 繼承規則

```
L1 Product (visibility: confidential)
  └── L2 Module A → 自動繼承 confidential
       └── L3 Detail → 自動繼承 confidential
       └── Document → 自動繼承 confidential
       └── Related Tasks → 自動繼承 confidential

L1 Product (visibility: public)
  └── L2 Module B (visibility: role-restricted, visible_to_roles: ["engineering"])
       └── L3 Detail → 自動繼承 role-restricted + engineering
       └── Document → 自動繼承 role-restricted + engineering
```

子節點可以**收緊**但不能**放寬**父節點的 visibility：
- 父 public → 子可以是 public / role-restricted / confidential
- 父 role-restricted → 子可以是 role-restricted（同角色或更少）/ confidential
- 父 confidential → 子只能是 confidential

### Action：能做什麼操作

| 操作 | admin | member（授權範圍內） | member（授權範圍外） |
|------|-------|-------------------|-------------------|
| search / get entity | ✅ 全部 | ✅ visible 的 | ❌ 不回傳 |
| read protocol | ✅ 全部 | ✅ visible entity 的 | ❌ 不回傳 |
| read blindspot | ✅ 全部 | ✅ visible entity 的 | ❌ 不回傳 |
| read task | ✅ 全部 | ✅ assigned 或 created 的 + visible entity 關聯的 | ❌ 不回傳 |
| write entity | ✅ 全部 | ✅ visible + writable 的 | ❌ 拒絕 |
| write task | ✅ 全部 | ✅ 可建立，linked_entities 限授權範圍 | ⚠️ 可建立但不能連結到不可見 entity |
| confirm entity | ✅ 全部 | ✅ visible 的 | ❌ 拒絕 |
| 設定 visibility | ✅ | ❌ | ❌ |
| 管理成員 | ✅ | ❌ | ❌ |

---

## 成員角色綁定

### Partner Schema 擴展

```typescript
interface Partner {
  // 既有欄位
  id: string;
  email: string;
  displayName: string;
  apiKey: string;
  isAdmin: boolean;
  status: "invited" | "active" | "suspended";

  // 新增
  roles: string[];              // 職能角色，如 ["marketing", "product"]
                                 // 對應 ontology Who 維度的值
                                 // admin 不需要 roles（自動看到全部）
}
```

### 角色來源

職能角色的定義來自 ontology 的 Who 維度（Entity 的 `tags.who` 欄位）。系統自動收集所有出現過的 who 值作為可選角色清單。

Admin 在 Team 頁面為每個成員指定角色：
```
Barry (admin)     → 不需要指定，看到全部
小美 (member)     → roles: ["marketing", "product"]
阿明 (member)     → roles: ["engineering"]
```

---

## 過濾機制

### Server 端過濾流程

```
MCP 請求進來
  → API key 認證 → 解析 partner（含 isAdmin, roles）
  → 注入 permission context（ContextVar）
  → tool handler 呼叫 service 層
  → service 層查 Firestore
  → 過濾引擎（permission filter）
      → 移除 visibility=confidential（除非 admin 或 visible_to_members 匹配）
      → 移除 visibility=role-restricted（除非 admin 或 roles 交集 visible_to_roles）
      → 計算繼承（父 restricted → 子也 restricted）
  → 回傳過濾後的結果
```

### 過濾點

| MCP Tool | 過濾位置 | 過濾方式 |
|---|---|---|
| `search` | OntologyService.search() | query 結果 post-filter |
| `get` | OntologyService.get_entity() | 單筆 visibility 檢查 |
| `write` | OntologyService.upsert_entity() | 寫入前 authorization 檢查 |
| `analyze` | GovernanceService.run_*() | 結果 post-filter |
| `confirm` | OntologyService.confirm() | 單筆 visibility 檢查 |
| `read_source` | SourceService | entity visibility 檢查 |

### Dashboard 過濾

Dashboard 直接讀 Firestore（不走 MCP）。兩個選項：

**選項 A：Dashboard 也走 MCP API**（推薦）
- 所有資料查詢統一走 MCP，server 端過濾
- 安全：過濾邏輯集中一處
- 缺點：Dashboard 需要 API key（從 partner.apiKey 取）

**選項 B：Firestore Rules 強化**
- 在 rules 裡檢查 visibility + 用戶角色
- 問題：Firestore rules 不支援複雜邏輯（繼承、角色交集），需要 denormalize

**PM 建議選項 A**：與「智慧邏輯放在 server 端」的原則一致。

---

## 需求

### P0（第一批實作——最小可用權限）

#### 1. Entity visibility 三級 + server 端過濾

- **描述**：Entity 支援 `public` / `role-restricted` / `confidential` 三級 visibility。所有 MCP search/get 回傳結果都經過 server 端 visibility 過濾。
- **驗收條件**：
  - Given entity A 是 `confidential`，When 非 admin member 的 agent 搜尋，Then 結果不包含 entity A
  - Given entity B 是 `role-restricted` + `visible_to_roles: ["engineering"]`，When marketing 角色的 agent 搜尋，Then 結果不包含 entity B
  - Given admin 搜尋，Then 看到所有 entity 包含 restricted 和 confidential
  - Given search 回傳 10 筆結果，其中 3 筆被過濾，Then API 回傳 7 筆（不是回傳 10 筆然後前端隱藏）

#### 2. Partner 角色綁定

- **描述**：Partner schema 新增 `roles: string[]` 欄位。Admin 可在 Team 頁面為成員指定角色。角色清單來自 ontology Who 維度的所有值。
- **驗收條件**：
  - Given admin 在 Team 頁面，When 為小美設定 roles=["marketing"]，Then 小美的 agent 只看到 public + marketing-visible entity
  - Given 新增成員未設角色，When 其 agent 搜尋，Then 只看到 `visibility: "public"` 的 entity

#### 3. Visibility 繼承

- **描述**：父 entity 的 visibility 自動繼承到子 entity、相關 document、protocol、blindspot。子節點可收緊但不能放寬。
- **驗收條件**：
  - Given L1 product 設為 confidential，When 非 admin 搜尋其下的 L2 module，Then 看不到
  - Given L1 public、L2 role-restricted(engineering)，When marketing 搜尋 L2 下的 L3，Then 看不到
  - Given admin 嘗試將 confidential 父節點下的子節點改為 public，Then 系統拒絕並提示原因

#### 4. Dashboard visibility 設定 UI

- **描述**：Admin 在 NodeDetailSheet（知識地圖的節點詳情面板）可以設定 entity 的 visibility。提供直覺的 UI：公開 / 限特定角色 / 機密。
- **驗收條件**：
  - Given admin 點開某 entity 的 NodeDetailSheet，Then 看到 visibility 設定區塊
  - Given admin 將 entity 改為 role-restricted + engineering，Then 保存成功，非 engineering 角色搜尋不到
  - Given 非 admin member 點開 NodeDetailSheet，Then 看不到 visibility 設定區塊

### P1（完善體驗）

#### 5. Write 操作的 authorization 檢查

- **描述**：非 admin member 的 agent 嘗試 write 不可見的 entity 時被拒絕。包含 upsert_entity、confirm、write relationship。
- **驗收條件**：
  - Given marketing member 的 agent 嘗試 write entity（visibility=confidential），Then 回傳 403 + 明確錯誤訊息
  - Given marketing member 的 agent 嘗試建立 relationship 到 confidential entity，Then 回傳 403

#### 6. Task visibility 連動

- **描述**：Task 的可見性跟著 `linked_entities` 走。如果 task 連結的所有 entity 對某成員都不可見，則該 task 也不可見。
- **驗收條件**：
  - Given task 連結到 confidential entity，When 非 admin 搜尋 tasks，Then 看不到該 task
  - Given task 連結到 2 個 entity（1 public + 1 confidential），When 非 admin 搜尋，Then **看得到 task**（至少有 1 個可見 entity）但 confidential entity 的資訊被遮蔽

#### 7. Blindspot / Protocol visibility 連動

- **描述**：Blindspot 和 Protocol 的可見性跟著關聯的 entity 走。
- **驗收條件**：
  - Given blindspot 關聯到 confidential entity，When 非 admin 執行 analyze，Then blindspot 不出現在結果中

#### 8. 權限變更 audit log

- **描述**：所有 visibility 變更和角色變更記錄到 audit log（Cloud Logging），包含 who/what/when/before/after。
- **驗收條件**：
  - Given admin 將 entity 從 public 改為 confidential，Then Cloud Logging 記錄變更詳情
  - Given admin 為 member 新增角色，Then Cloud Logging 記錄角色變更

### P2（進階場景）

#### 9. 來源層權限同步

- **描述**：當 Adapter 從 Google Drive / GitHub 讀取文件時，如果原始文件有存取限制（如 Drive ACL），自動將對應的 entity 標記為 role-restricted。
- **備註**：這是 Adapter 成熟後的功能，目前不需要。

#### 10. 批次 visibility 設定

- **描述**：Admin 可以在 Dashboard 上選擇多個 entity 批次設定 visibility。
- **備註**：ontology 初期 entity 量不大，逐個設定可接受。

---

## 不做的事

- **Per-entity per-member ACL**：不做「entity-123 只有 member-456 能看」的細粒度（confidential + visible_to_members 是極端情況的逃生口，不是常態操作）
- **自訂角色分級**：不做「engineering-senior 能看但 engineering-junior 不能看」的角色階層
- **時間限制**：不做「entity-123 在 2026-04-01 之前是 confidential」的時間維度
- **跨公司權限**：不在此 spec 範圍（屬於 SPEC-multi-tenant）

---

## 對現有架構的影響

### Entity Domain Model

```python
@dataclass
class Entity:
    # 既有
    visibility: str = "public"
    owner: str | None = None

    # 新增
    visible_to_roles: list[str] = field(default_factory=list)
    visible_to_members: list[str] = field(default_factory=list)
```

### Permission Context

```python
@dataclass
class PermissionContext:
    partner_id: str
    is_admin: bool
    roles: list[str]         # partner.roles
    display_name: str
```

注入到每個 MCP 請求的 ContextVar，service 層從 context 取得後進行過濾。

### 受影響的主要檔案

| 檔案 | 改動 |
|------|------|
| `src/zenos/domain/models.py` | Entity 新增 visible_to_roles / visible_to_members |
| `src/zenos/application/ontology_service.py` | 所有 search/get 加過濾邏輯 |
| `src/zenos/application/governance_service.py` | analyze 結果過濾 |
| `src/zenos/application/task_service.py` | task search 結果過濾 |
| `src/zenos/interface/tools.py` | PermissionContext 注入 |
| `src/zenos/infrastructure/firestore_repo.py` | Partner schema 擴展 |
| `dashboard/src/app/team/page.tsx` | 角色管理 UI |
| `dashboard/src/components/NodeDetailSheet.tsx` | visibility 設定 UI |
| `firestore.rules` | Partner 新增 roles 欄位的 read rule |

---

## 用戶故事

1. **作為老闆**，我想把「薪資結構」entity 設為機密，這樣行銷 agent 寫文案時不會引用到薪資資訊
2. **作為老闆**，我想讓工程架構只對 engineering 角色可見，這樣行銷 agent 不會被技術細節干擾，能更專注在產品價值上
3. **作為行銷主管**，我不需要手動設定任何權限，老闆設好之後我的 agent 自動只看到該看的
4. **作為新進員工**，我的 agent 查 ontology 時看到的都是我能看的，不會意外看到老闆的薪資評估或客戶合約
5. **作為老闆**，我剛開始用 ZenOS 時不想設任何權限（全部 public），等 ontology 穩定了再逐步標記敏感資訊

---

## 與其他 Spec 的關係

| Spec | 關係 |
|------|------|
| SPEC-multi-tenant | 本 spec 處理**公司內**權限；multi-tenant 處理**公司間**隔離。互不衝突。 |
| SPEC-partner-context-fix | 前置依賴。Dashboard 必須先能正確解析 partner identity，才能做 visibility 過濾。 |
| SPEC-governance-audit-log | P1 的權限變更 audit log 依賴 audit log 基礎設施。 |
| spec.md Part 7.6 | 本 spec 是 Part 7.6 權限模型的完整展開。實作後需回更 Part 7.6。 |
| spec.md Part 5 漸進式信任 | 權限的漸進式策略（預設開放→逐步收緊）對齊漸進式信任哲學。 |

---

## 成功指標

- **短期（2 週）**：Admin 能在 Dashboard 標記 entity 為 confidential，非 admin agent 搜尋不到
- **中期（1 個月）**：角色綁定運作，marketing agent 只看到 public + marketing-visible entity
- **長期指標**：客戶願意把敏感資訊放進 ontology（衡量標準：ontology 中 confidential entity 佔比 > 0，代表客戶信任這個系統）

---

## 開放問題

1. **visibility 預設值**：新建 entity 預設 `public` 還是讓 GovernanceAI 根據內容自動推薦？（例如名稱包含「薪資」「合約」自動建議 confidential）
2. **角色粒度**：ontology Who 維度的值可能很細（如 `marketing-content`, `marketing-ads`），Team 頁面是否需要角色群組功能？還是直接用 Who 的值？
3. **Dashboard 查詢走 MCP 的遷移時程**：如果選擇選項 A（所有查詢走 MCP），前端需要大幅改動。是否在此 spec 範圍內一併處理？
