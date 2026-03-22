# Dashboard v0 — 技術設計

> 日期：2026-03-21
> 作者：Architect
> 依據：`docs/specs/dashboard-v0.md`（PM Feature Spec）
> 狀態：Draft — 待 Barry 確認後開始實作

---

## PM 開放問題回覆

逐一回覆 PM spec 的 6 個開放問題：

### 1. 技術棧選型

**結論：Next.js 15（App Router）+ Tailwind CSS + Firebase JS SDK**

| 選項 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| Next.js 15 | 檔案路由、React 生態、TypeScript 原生、未來擴充方便 | 比純 SPA 重 | ✅ 選這個 |
| Vite + React | 更輕、建構快 | 需手動加 router，結構鬆散 | ❌ |
| 純靜態 + Firebase SDK | 最輕 | 沒有框架結構，難以擴充 | ❌ |

理由：Dashboard v0 只有 4 頁，但後續會加確認佇列、Protocol viewer 等功能。Next.js 提供的結構（App Router + layout）讓擴充成本很低。

### 2. 部署位置

**結論：Vercel（免費方案足夠）**

| 選項 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| Vercel | Next.js 原生支援、零設定部署、preview deploy | 免費方案有限制 | ✅ |
| Firebase Hosting | 同一個 GCP project | 對 Next.js 的 SSR 支援不完整 | ❌ |
| Cloud Run | 已經跑 MCP server | 需要自己管 Docker，過重 | ❌ |

### 3. API key 管理

**結論：Firestore `partners` collection + MCP server 多 key 驗證**

目前 MCP server 用單一環境變數 `ZENOS_API_KEY` 做驗證。要支援多夥伴，改為 Firestore 驗證。

```
partners/{partnerId}
  email           string    必填    Google 登入的 email
  displayName     string    必填    顯示名稱
  apiKey          string    必填    自動產生的 UUID v4
  authorizedEntityIds  string[]  必填    可存取的 product entity ID
  isAdmin         boolean   必填    是否為管理員（Barry = true）
  status          string    必填    "active" | "suspended"
  createdAt       timestamp 必填
  updatedAt       timestamp 必填
```

**MCP server 改動：**
- 收到請求時，從 `partners` collection 查找 `apiKey` 匹配的文件
- 加入 in-memory cache（TTL 5 分鐘），避免每次請求都讀 Firestore
- `ZENOS_API_KEY` 環境變數保留為 superadmin key（backward compatible）

### 4. 夥伴與專案的關聯

**結論：用 `authorizedEntityIds` 控制，「專案」= `type: "product"` 的 entity**

Dashboard 裡的「專案」不需要另開 collection，就是骨架層裡 `type: "product"` 的 entity。夥伴文件的 `authorizedEntityIds` 存的是這些 product entity 的 ID。

查詢邏輯：
1. 讀當前用戶的 partner document → 拿到 `authorizedEntityIds`
2. 用 `where('id', 'in', authorizedEntityIds)` 查 entities
3. 每個 product entity 的子模組用 `where('parentId', '==', productEntityId)` 查

### 5. 「測試連線」功能

**結論：v0 不做。改用文字提示。**

理由：MCP server 用 SSE transport，不適合做簡單的 health check。要做需要加一個獨立的 REST endpoint，投入不值得。

替代方案：設定步驟的最後一步寫「在 Claude Code 輸入 `列出所有產品`，如果有回應就代表設定成功」。

### 6. ontology 概覽的資料來源

**結論：直接讀 Firestore（Firebase JS SDK client-side）**

| 選項 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| 直接讀 Firestore | 最快、不經過中間層、Security Rules 控制存取 | Dashboard 和 MCP server 耦合同一個 DB | ✅ |
| 透過 MCP server API | 解耦 | MCP 是給 AI agent 用的（SSE），不適合 REST 風格 UI 查詢 | ❌ |

MCP server 是 AI agent 的介面，Dashboard 是人的介面。兩者讀同一份 Firestore 資料，但走不同的存取路徑。

---

## 架構總覽

```
┌──────────────────┐     ┌──────────────────┐
│  Dashboard       │     │  MCP Server      │
│  (Next.js/Vercel)│     │  (Python/Cloud Run)│
│                  │     │                  │
│  Firebase Auth   │     │  API Key Auth    │
│  Firestore SDK   │     │  Firestore SDK   │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         │    讀取                 │    讀寫
         ▼                        ▼
┌──────────────────────────────────────────┐
│  Firestore (zenos-naruvia)               │
│                                          │
│  entities/          ← 骨架層             │
│  documents/         ← 神經層             │
│  protocols/         ← Context Protocol   │
│  blindspots/        ← 盲點分析           │
│  partners/          ← 新增：夥伴管理     │
└──────────────────────────────────────────┘
```

**Dashboard 只做讀取，不做寫入**（除了 Barry 的管理功能）。
所有 ontology 的寫入都走 MCP server（Barry 的 Claude Code session）。

---

## 前端架構

### 目錄結構

```
dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx              ← 全域 layout（AuthProvider）
│   │   ├── page.tsx                ← 首頁：我的專案
│   │   ├── login/
│   │   │   └── page.tsx            ← 登入頁
│   │   ├── setup/
│   │   │   └── page.tsx            ← MCP 設定指引
│   │   └── projects/
│   │       └── [projectId]/
│   │           └── page.tsx        ← 專案 ontology 概覽
│   ├── components/
│   │   ├── AuthGuard.tsx           ← 認證守衛（未登入 → /login）
│   │   ├── ProjectCard.tsx         ← 專案卡片
│   │   ├── EntityTree.tsx          ← 模組樹狀圖
│   │   ├── BlindspotAlert.tsx      ← 盲點警示
│   │   ├── McpConfigBlock.tsx      ← Config JSON + 複製按鈕
│   │   └── PromptSuggestions.tsx   ← 範例 prompt 卡片
│   ├── lib/
│   │   ├── firebase.ts             ← Firebase 初始化（Auth + Firestore）
│   │   ├── auth.tsx                ← AuthContext + useAuth hook
│   │   └── firestore.ts            ← Firestore 查詢函數
│   └── types/
│       └── index.ts                ← TypeScript 型別定義
├── public/
├── next.config.ts
├── tailwind.config.ts
├── package.json
└── tsconfig.json
```

### 資料流

```
1. 用戶打開 Dashboard
   → AuthGuard 檢查 Firebase Auth 狀態
   → 未登入 → redirect /login
   → 已登入 → 查 partners collection（email 匹配）
   → 找不到 partner → 顯示「請聯繫管理員」
   → 找到 → 存入 AuthContext（partner data + authorizedEntityIds）

2. 首頁載入
   → 從 AuthContext 拿 authorizedEntityIds
   → 查 entities（type=product, id in authorizedEntityIds）
   → 渲染 ProjectCard 列表

3. 專案概覽頁載入
   → 用 projectId 查 entity（驗證在 authorizedEntityIds 中）
   → 查子 entities（parentId = projectId）
   → 查 relationships（source_entity_id in [projectId + 子 entity IDs]）
   → 查 blindspots（related_entity_ids 包含 projectId）
   → 查 documents count（linked_entity_ids 包含 projectId）
   → 渲染全景圖
```

---

## Firestore Schema 變更

### 新增：partners collection

```
partners/{partnerId}
  email               string      必填    Google 登入的 email（唯一索引）
  displayName         string      必填    顯示名稱
  apiKey              string      必填    UUID v4，MCP 認證用
  authorizedEntityIds string[]    必填    可存取的 product entity ID 列表
  isAdmin             boolean     必填    管理員標記
  status              string      必填    "active" | "suspended"
  createdAt           timestamp   必填
  updatedAt           timestamp   必填
```

### Firestore Security Rules 更新

```javascript
rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {

    // Partners：只能讀自己的文件，寫入只有 admin
    match /partners/{partnerId} {
      allow read: if request.auth != null
                  && resource.data.email == request.auth.token.email;
      allow write: if false;  // 只有 Admin SDK（MCP server / Barry）能寫
    }

    // Ontology collections：已登入用戶可讀，寫入只有 Admin SDK
    match /entities/{entityId} {
      allow read: if request.auth != null;
      allow write: if false;  // MCP server 用 service account 寫入

      match /relationships/{relId} {
        allow read: if request.auth != null;
        allow write: if false;
      }
    }

    match /documents/{docId} {
      allow read: if request.auth != null;
      allow write: if false;
    }

    match /protocols/{protocolId} {
      allow read: if request.auth != null;
      allow write: if false;
    }

    match /blindspots/{blindspotId} {
      allow read: if request.auth != null;
      allow write: if false;
    }
  }
}
```

**設計選擇：** ontology 資料的存取控制在 UI 層（用 `authorizedEntityIds` 過濾），不在 Security Rules 層。因為：
- entities 之間有 relationship 交叉引用，rules 層做不到跨 collection 的權限判斷
- v0 的安全需求低（夥伴都是 Barry 信任的人）
- 主要目標是防止未認證存取，不是防夥伴看到其他專案

---

## MCP Server 改動

### ApiKeyMiddleware 升級為多 key 驗證

```python
# 新增：PartnerKeyValidator
class PartnerKeyValidator:
    """Validates API keys against Firestore partners collection."""

    def __init__(self):
        self._cache: dict[str, dict] = {}   # key -> partner data
        self._cache_ts: float = 0
        self._ttl = 300  # 5 minutes

    async def validate(self, key: str) -> dict | None:
        """Return partner data if key valid, None otherwise."""
        now = time.time()
        if now - self._cache_ts > self._ttl:
            await self._refresh_cache()

        return self._cache.get(key)

    async def _refresh_cache(self):
        db = get_db()
        docs = db.collection("partners").where("status", "==", "active").stream()
        new_cache = {}
        async for doc in docs:
            data = doc.to_dict()
            api_key = data.get("apiKey", "")
            if api_key:
                new_cache[api_key] = data
        self._cache = new_cache
        self._cache_ts = time.time()
```

**Backward compatible：** 原本的 `ZENOS_API_KEY` 環境變數繼續作為 superadmin key，不走 Firestore 驗證。

---

## 安全審查

```
✅ Secrets 管理：Firebase config 用環境變數，API key 存 Firestore 不存 code
✅ 認證：Firebase Auth（Google）+ partner document 驗證
✅ 授權：UI 層用 authorizedEntityIds 過濾，Firestore Rules 擋未認證存取
✅ 寫入保護：所有 ontology collection 的 write = false（只有 Admin SDK 能寫）
⚠️ 不在 v0 scope：多租戶 tenantId 隔離（v0 是單租戶）
⚠️ 不在 v0 scope：API key 輪換機制
```

---

## 實作任務拆分

### Task 1：Dashboard 前端基礎建設

**角色：** Developer
**預估：** 1 天

**Done Criteria：**
- [ ] Next.js 15 + Tailwind + TypeScript 專案初始化在 `dashboard/` 目錄
- [ ] Firebase JS SDK 設定完成（Auth + Firestore）
- [ ] AuthContext + useAuth hook 實作
- [ ] AuthGuard 元件：未登入 → /login，已登入但非 partner → 錯誤頁
- [ ] Layout 包含 header（logo + 使用者名 + 登出）
- [ ] 登入頁（Google 登入按鈕）可正常登入/登出
- [ ] 能在 local dev 跑起來

**技術參考：**
- Firebase project: `zenos-naruvia`
- 需要在 Firebase Console 啟用 Authentication（Google provider）

---

### Task 2：Firestore partners collection + seed data

**角色：** Developer
**預估：** 半天

**Done Criteria：**
- [ ] Firestore Security Rules 更新（如上方設計）
- [ ] 部署更新後的 rules 到 zenos-naruvia
- [ ] 手動建立 Barry 的 partner document（isAdmin: true）
- [ ] 手動建立測試用行銷夥伴的 partner document
- [ ] 兩筆 partner 的 apiKey 都是有效的 UUID v4
- [ ] `authorizedEntityIds` 包含現有的 Paceriz product entity ID

---

### Task 3：MCP server 多 key 驗證

**角色：** Developer
**預估：** 半天

**Done Criteria：**
- [ ] `PartnerKeyValidator` class 實作，含 5 分鐘 TTL cache
- [ ] `ApiKeyMiddleware` 改為：先查 `ZENOS_API_KEY` 環境變數（superadmin），再查 Firestore
- [ ] 原有的單 key 行為不變（backward compatible）
- [ ] 本地測試：用 partner 的 apiKey 能存取 MCP tools
- [ ] 重新部署到 Cloud Run
- [ ] 部署後驗證：用新 key 和舊 key 都能存取

---

### Task 4：首頁 + 專案卡片

**角色：** Developer
**預估：** 半天

**Done Criteria：**
- [ ] `/` 路由：顯示當前用戶被授權的專案列表
- [ ] 專案卡片包含：名稱、一句話描述（entity.summary）、模組數量、最後更新時間
- [ ] 頂部有 CTA 按鈕「設定你的 AI Agent」→ 連到 /setup
- [ ] 空狀態處理：沒有被授權的專案時顯示提示
- [ ] 點擊卡片 → 導航到 `/projects/[entityId]`

---

### Task 5：MCP 設定指引頁

**角色：** Developer
**預估：** 1 天

**Done Criteria：**
- [ ] `/setup` 路由：讀取當前用戶的 partner document，取得 apiKey
- [ ] API key 顯示區：預設遮罩（`zenos_••••••••`），點擊顯示完整 key
- [ ] Agent 類型 Tab（Claude Code / Claude.ai / 其他）
- [ ] 根據選擇的 agent 類型，動態生成對應的 config JSON
- [ ] Config JSON 包含正確的 Cloud Run URL + 該用戶的 apiKey
- [ ] 一鍵複製按鈕（複製後顯示「已複製」回饋）
- [ ] Step-by-step 設定步驟（可折疊）
- [ ] 最後一步提示「在 Claude Code 輸入 `列出所有產品` 驗證」

---

### Task 6：專案 Ontology 概覽頁

**角色：** Developer
**預估：** 1 天

**Done Criteria：**
- [ ] `/projects/[projectId]` 路由：驗證 projectId 在 authorizedEntityIds 中
- [ ] 區塊 A — 專案摘要：名稱、summary、統計數字（模組數、文件數、盲點數）
- [ ] 區塊 B — 模組全景：按 type 分組的 entity 卡片，每個有名稱/狀態/summary
- [ ] 模組卡片可展開看 relationships（依賴什麼、被誰依賴）
- [ ] 區塊 C — 盲點摘要：red/yellow 盲點列表，含描述和建議動作
- [ ] 區塊 D — 範例 prompt 卡片：3-5 個範例，動態替換專案名稱，可複製
- [ ] 紅色盲點在頁面頂部顯示醒目警示
- [ ] 未授權的 projectId → redirect 首頁

---

### Task 7：Vercel 部署 + 網域

**角色：** Developer
**預估：** 半天

**Done Criteria：**
- [ ] Dashboard 部署到 Vercel
- [ ] 環境變數設定（Firebase config）
- [ ] 設定自訂網域（如 `dashboard.zenos.app` 或類似）⚠️ 待 Barry 確認網域
- [ ] Firebase Auth 的 authorized domains 加入 Vercel 網域
- [ ] 部署後 E2E 驗證：登入 → 看到專案 → 進 setup → 複製 config → 看到概覽

---

### Task 8：QA 驗收

**角色：** QA
**依賴：** Task 1-7 全部完成
**預估：** 半天

**P0 驗收條件（來自 PM spec）：**
- [ ] 行銷夥伴從登入到完成 MCP 設定，全程不需要問 Barry
- [ ] 行銷夥伴看完 ontology 概覽後，能說出「這個產品大概在做什麼」
- [ ] 行銷夥伴複製範例 prompt、貼到 Claude Code、拿到有 context 的回應
- [ ] Barry 能在 10 分鐘內幫新夥伴開好帳號

**測試情境：**
- [ ] 未授權帳號登入 → 看到「請聯繫管理員」
- [ ] 已授權夥伴登入 → 看到正確的專案列表（只有自己被授權的）
- [ ] MCP config 複製貼上到 Claude Code → 能成功查詢 ontology
- [ ] 專案概覽頁的模組/盲點/prompt 都有正確資料
- [ ] 手機瀏覽器基本可用（不需要完美 RWD，但不能壞掉）

---

## 執行順序

```
Week 1
├── Task 1：前端基礎建設（1天）
├── Task 2：Firestore partners + seed data（半天）── 可與 Task 1 並行
├── Task 3：MCP server 多 key 驗證（半天）── 可與 Task 1 並行
├── Task 4：首頁 + 專案卡片（半天）── 依賴 Task 1+2
├── Task 5：MCP 設定指引頁（1天）── 依賴 Task 1+2
└── Task 6：專案概覽頁（1天）── 依賴 Task 1+2

Week 2
├── Task 7：部署（半天）── 依賴 Task 1-6
└── Task 8：QA 驗收（半天）── 依賴 Task 7
```

**關鍵路徑：** Task 1 → Task 4/5/6（並行）→ Task 7 → Task 8
**可並行：** Task 2 和 Task 3 可以跟 Task 1 同時做

---

*Architect 交付。技術決策如有疑問請 Barry 確認後再開始實作。*
