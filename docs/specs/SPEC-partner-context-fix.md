---
type: SPEC
id: SPEC-partner-context-fix
status: Draft
ontology_entity: identity-and-access
created: 2026-03-25
updated: 2026-04-23
depends_on: SPEC-identity-and-access
---

# SPEC: 修復 Partner Context——Dashboard 自動解析身份，多人共享資料

> PM: Claude (PM role) | Status: Draft（frontmatter 標準化於 2026-04-23）

## 問題

Dashboard 的 Firestore 查詢（tasks、entity-linked tasks）依賴 build-time 環境變數 `NEXT_PUBLIC_PARTNER_ID` 決定 partner scope。這個變數：

1. **沒有被設定**（`.env.local` 不存在）→ Tasks 分頁永遠空白
2. **是 build-time 寫死的** → 部署給不同公司需要重新 build → 不可能
3. **跟登入身份無關** → 即使用戶已登入，Dashboard 也不知道他屬於哪個 partner

結果：**MCP 建立的任務在 Dashboard 看不到**。第二個人加入時更嚴重——每個人的 `partner.id` 不同，各自的 MCP agent 把任務寫到不同的 subcollection，Dashboard 只能看到一個人的（或根本看不到任何人的）。

### 根本原因

`auth.tsx` 登入後已經拿到 `partner.id`（Firestore document ID），但 `firestore.ts` 沒有用它，而是讀一個不存在的環境變數。

### 更深的問題：誰的 partner ID？

目前 `partners/{partnerId}/tasks` 的設計假設每個人有自己的 task subcollection。但這造成：

- Barry 的 agent 建任務 → 寫到 `partners/xm6.../tasks`
- 同事 A 的 agent 建任務 → 寫到 `partners/Dcb.../tasks`
- **兩人看不到彼此的任務** → 協作斷裂

Phase 0 的 SPEC-multi-tenant.md 已經定義：**一個 Firebase Project = 一家公司**，`partners` collection 裡所有人都是同一家公司的成員。所以 tasks 應該用**公司級**的共享空間，不是個人級的 subcollection。

---

## 目標

1. Dashboard 登入後**自動**從 auth context 取得 partner ID，不需任何環境變數
2. 同一家公司的所有成員**共享同一份 tasks**，不因 partner ID 不同而看到不同資料
3. 不破壞現有 MCP backend 的 API key 認證機制
4. 為未來多租戶（多 Firebase Project）預留乾淨的擴展路徑

## 非目標

- 不重構 Firestore collection 結構（不動 backend schema）
- 不做跨公司資料隔離（Phase 0 只有一家公司）
- 不做 entity/document/protocol 的 partner scope（目前是全域，跟著 multi-tenant spec 再動）

---

## 現狀分析

### 資料流

```
MCP Agent 寫入任務
  → API key 認證 → 解析 partner_id（從 apiKey 對應的 partner doc ID）
  → 寫入 partners/{partner_id}/tasks/{task_id}

Dashboard 讀取任務
  → 用戶 Google 登入 → auth.tsx 查到 partner（含 partner.id）
  → firestore.ts 讀 NEXT_PUBLIC_PARTNER_ID（空字串）
  → 查根層 tasks collection（空的）
  → 顯示 0 筆任務 ❌
```

### 為什麼現在 tasks 分頁是空的

| 步驟 | 預期 | 實際 |
|------|------|------|
| auth.tsx 登入 | 拿到 partner.id = `xm6YB5DH2d4BMu5g0Ka2` | ✅ 正確 |
| firestore.ts 取 PARTNER_ID | 從 auth context 取 partner.id | ❌ 讀環境變數（空字串） |
| 查詢路徑 | `partners/xm6.../tasks` | ❌ `tasks`（根層，空的） |

### 多人場景的問題

假設 Barry（partner ID: `xm6...`）和同事 Alice（partner ID: `DcB...`）：

| 操作 | 資料位置 |
|------|---------|
| Barry 的 agent 建任務 | `partners/xm6.../tasks/task-1` |
| Alice 的 agent 建任務 | `partners/DcB.../tasks/task-2` |
| Barry 開 Dashboard | 只看到 `partners/xm6.../tasks`（看不到 Alice 的 task-2） |
| Alice 開 Dashboard | 只看到 `partners/DcB.../tasks`（看不到 Barry 的 task-1） |

**結果：同一家公司的兩個人無法看到彼此的任務。**

---

## 設計方案

### Phase 0 修復（最小改動，立即可用）

Phase 0 的前提：**一個 Firebase Project = 一家公司**，所有 `partners` 都是同一家公司的人。

#### 前端改動

**1. `firestore.ts`：從 auth context 取 partner ID，移除環境變數**

```
Before: const PARTNER_ID = process.env.NEXT_PUBLIC_PARTNER_ID ?? "";
After:  getTasks(partnerId, filters) — partnerId 由 caller 傳入
```

所有查詢函式（`getTasks`、`getEntityLinkedTasks`）增加 `partnerId` 參數，由頁面組件從 `useAuth().partner.id` 傳入。

**2. Tasks 頁面 / Knowledge Map 頁面：傳入 partner.id**

```typescript
const { partner } = useAuth();
const tasks = await getTasks(partner.id, filters);
```

#### 後端改動（Phase 0 不動）

Phase 0 不需要改 backend。每個人的 MCP agent 用自己的 API key，tasks 寫到自己的 `partners/{id}/tasks` 底下。前端暫時只查自己的 partner scope——**這意味著 Phase 0 多人場景下，每人只看到自己 agent 建的任務**。

這是 Phase 0 的已知限制，不是 bug。真正的修復在 Phase 1。

---

### Phase 1 方案：共享任務空間

當需要多人協作時，tasks 需要用**公司級**的共享路徑。

#### 方案 A：統一 tasks 到根層 collection + project 欄位隔離

```
/tasks/{taskId}
  ├── project: "zenos"
  ├── created_by: "Barry"
  └── ...全部任務混在一起，靠 query filter 隔離
```

- 優點：簡單，一個 collection 就好
- 缺點：跨公司時靠 code 隔離，不是物理隔離（SPEC-multi-tenant 明確反對）

#### 方案 B：引入 company 層級，tasks 掛在 company 下

```
/companies/{companyId}
  ├── members/        ← 原 partners collection 的資料
  │   ├── {memberId}  (email, displayName, apiKey, isAdmin, status)
  │   └── ...
  ├── tasks/          ← 公司共享
  │   ├── {taskId}
  │   └── ...
  ├── entities/       ← 公司共享（目前在根層，未來遷移）
  └── apiKeys/        ← 可選：公司級 key vs 個人級 key
```

- 優點：物理隔離、語意清楚、對齊 SPEC-multi-tenant
- 缺點：需要 migration、backend 改動較大

#### PM 建議

**Phase 0 用最小修復（前端從 auth context 取 partner ID）**，讓 Dashboard 至少能看到自己的任務。

**Phase 1 用方案 B**，但這是 SPEC-multi-tenant 的範圍，不在這個 spec 裡重複定義。這個 spec 只負責 Phase 0 的前端修復。

---

## 需求

### P0（立即修復）

#### 1. Dashboard 從登入身份自動取得 partner ID

- **描述**：移除 `NEXT_PUBLIC_PARTNER_ID` 環境變數依賴。`firestore.ts` 的查詢函式接受 `partnerId` 參數，由頁面組件從 `useAuth().partner.id` 傳入。
- **驗收條件**：
  - Given 用戶已登入且 partner 存在
  - When 開啟 Tasks 分頁
  - Then 看到該 partner 下的所有任務
  - And 不需要設定任何環境變數

#### 2. 未登入或無 partner 時的 graceful fallback

- **描述**：如果 `partner` 為 null（未登入 / email 不在 partners 裡），查詢函式應回傳空陣列，不 crash。
- **驗收條件**：
  - Given 用戶未登入
  - When 嘗試讀取 tasks
  - Then 回傳空陣列，不拋錯

#### 3. Knowledge Map 的 entity-linked tasks 同步修復

- **描述**：`getEntityLinkedTasks(entityId)` 也依賴 `PARTNER_ID`（`firestore.ts:273`），需同步改為接受 `partnerId` 參數。
- **驗收條件**：
  - Given 用戶在知識地圖點擊節點
  - When NodeDetailSheet 載入關聯任務
  - Then 正確顯示該 partner 下關聯的任務

#### 4. 移除 NEXT_PUBLIC_PARTNER_ID 的所有引用

- **描述**：確保 codebase 中沒有遺留的 `NEXT_PUBLIC_PARTNER_ID` 引用。
- **驗收條件**：
  - `grep -r "NEXT_PUBLIC_PARTNER_ID" dashboard/` 回傳 0 筆

### P1（多人可見性，Phase 1 範圍）

#### 5. 同一家公司的成員共享任務視圖

- **描述**：同公司的多個成員開 Dashboard 時，應看到相同的 tasks pool（不限於自己 agent 建的）。
- **備註**：這需要 backend 改動（tasks 統一到公司級 collection），屬於 SPEC-multi-tenant 範圍。此處僅標記需求，不定義實作。

---

## 受影響的檔案

| 檔案 | 改動類型 | 說明 |
|------|---------|------|
| `dashboard/src/lib/firestore.ts` | **修改** | 移除 `NEXT_PUBLIC_PARTNER_ID`，`getTasks` / `getEntityLinkedTasks` 加 `partnerId` 參數 |
| `dashboard/src/app/tasks/page.tsx` | **修改** | 從 `useAuth()` 取 `partner.id` 傳入 `getTasks` |
| `dashboard/src/app/knowledge-map/page.tsx` | **修改** | 傳入 `partner.id` 給 `getEntityLinkedTasks` |
| `dashboard/src/components/NodeDetailSheet.tsx` | **修改** | 接收 `partnerId` prop 傳入 task 查詢 |

不需改動：
- Backend（MCP server、admin API）— Phase 0 不動
- Firestore rules — 現有規則已支援 `partners/{partnerId}/tasks` 的 read
- auth.tsx — 已正確解析 partner

---

## 已知限制（Phase 0）

1. **多人場景下每人只看到自己的任務**：因為每個 partner 有獨立的 tasks subcollection，前端只查自己的。這是 Phase 0 的架構限制，Phase 1（SPEC-multi-tenant）會解決。
2. **Dashboard 上手動建立的任務無法指定 partner**：Dashboard 目前是唯讀（tasks 透過 MCP agent 建立），如果未來加 UI 建任務功能，需要知道寫到哪個 partner 下。

---

## 測試計畫

1. **冒煙測試**：登入 → Tasks 分頁顯示任務 → 數量與 MCP search 一致
2. **Knowledge Map**：點擊節點 → NodeDetailSheet 顯示關聯任務
3. **無 partner 場景**：未邀請的 email 登入 → 顯示「尚未開通權限」，不 crash
4. **清除 env var 驗證**：確認不存在 `.env.local` 時 Dashboard 仍正常運作
