# 用戶邀請與權限管理 MVP — 技術設計

> Architect handoff for `docs/archive/specs/deferred-2026-03/SPEC-user-invitation-mvp.md`

## PM 開放問題的技術回答

### Q1: FastMCP tool handler 能否拿到 partner data？

**結論：可行，用 Python `contextvars.ContextVar`。**

FastMCP 2.0 的 tool handler 是 plain async function，沒有內建 request context 機制。
但 ASGI middleware 和 tool handler 跑在同一個 async 執行緒，所以 `ContextVar` 天然可用。

```python
from contextvars import ContextVar

# 全域定義
_current_partner: ContextVar[dict | None] = ContextVar("current_partner", default=None)

# ApiKeyMiddleware 驗證成功後設定
_current_partner.set(partner_data)

# tool handler 讀取
partner = _current_partner.get()
if partner:
    created_by = partner["displayName"]
```

不依賴 FastMCP 內部 API，穩定可靠。

### Q2: Firebase email link + Google SSO 整合方式？

**結論：用 `sendSignInLinkToEmail` 發邀請信，登入頁面處理 email link sign-in。**

流程：
1. Admin 在 `/team` 輸入 email → Dashboard 呼叫後端 API 建立 partner doc（status="invited"）
2. Dashboard 用 Firebase Auth SDK `sendSignInLinkToEmail(email, settings)` 發邀請信
3. 被邀請者收到 Firebase 發的 email → 點擊連結到 Dashboard `/login`
4. 登入頁面偵測 `isSignInWithEmailLink(window.location.href)` → 完成 email link sign-in
5. AuthGuard 查到 partner doc status="invited" → 自動啟用（生成 API key，status→"active"）

技術要點：
- Firebase console 需啟用 Email link sign-in provider
- `actionCodeSettings.url` 指向 `https://zenos-naruvia.web.app/login`
- 被邀請者用 email link 登入（不需要 Google OAuth），後續可在登入頁選擇 Google 登入
- 同一 email 的 Firebase Auth 會自動合併不同 provider

### Q3: Dashboard 寫 Firestore 走什麼？

**結論：在既有 Cloud Run server 加 REST endpoints，用 Firebase ID token 驗證。**

不新增 Cloud Functions（避免維護第二套部署），不開放 Firestore rules（維持 Admin SDK 集中寫入原則）。

在 MCP server 的 Starlette app 掛載額外路由：
```
POST /api/partners/invite     — 建立 invited partner
PUT  /api/partners/{id}/role  — 修改 isAdmin
PUT  /api/partners/{id}/status — 修改 status（active/suspended）
GET  /api/partners/{id}/activate — 首次登入啟用（生成 API key）
```

Auth 分流：
- `/mcp/*` → API key auth（既有，給 AI agent 用）
- `/api/*` → Firebase ID token auth（新增，給 Dashboard 用）

`ApiKeyMiddleware` 跳過 `/api/` 路徑，admin API 自行驗證 Firebase ID token + admin 權限。

---

## 架構設計

### 整體流程

```
┌─────────────┐     Firebase ID token      ┌─────────────────────┐
│  Dashboard   │ ─── POST /api/invite ────→ │  Cloud Run Server   │
│  /team page  │                            │  (MCP + Admin API)  │
│              │ ← 200 OK ────────────────  │                     │
│              │                            │  Firestore: partners│
│  sendSignIn  │                            │  status="invited"   │
│  LinkToEmail │                            └─────────────────────┘
└──────┬───────┘
       │ Firebase sends email
       ▼
┌─────────────┐
│  被邀請者    │  clicks link
│  email      │ ────────────→  /login?signInLink=...
└─────────────┘
                               ┌─────────────────────┐
                               │  Login Page          │
                               │  isSignInWithEmail   │
                               │  Link() → sign in   │
                               │                     │
                               │  AuthGuard:          │
                               │  partner.status ==   │
                               │  "invited" →        │
                               │  call /api/activate  │
                               │  → status="active"   │
                               │  → generate apiKey   │
                               └─────────────────────┘
```

### MCP Server 改動

#### A. ContextVar 注入 partner identity

```python
# tools.py 新增
from contextvars import ContextVar

_current_partner: ContextVar[dict | None] = ContextVar("current_partner", default=None)

# ApiKeyMiddleware.__call__ 修改
async def __call__(self, scope, receive, send):
    # ... 驗證成功後 ...
    if partner is not None:
        _current_partner.set(partner)  # 注入 partner data
        return await self.app(scope, receive, send)

# task tool handler 修改
async def task(action, title, created_by=None, ...):
    if action == "create":
        if not created_by:
            partner = _current_partner.get()
            if partner:
                created_by = partner.get("displayName", "unknown")
```

#### B. Admin REST API

新增 `src/zenos/interface/admin_api.py`：

```python
from starlette.routing import Route
from firebase_admin import auth as firebase_auth

async def invite_partner(request):
    """POST /api/partners/invite { email: str }"""
    # 1. 驗證 Firebase ID token
    # 2. 查 caller 是否 admin
    # 3. 檢查 email 是否已存在
    # 4. 建立 partner doc (status="invited", apiKey="", invitedBy=caller.email)
    # 5. 回傳 partner data

async def update_partner_role(request):
    """PUT /api/partners/{id}/role { isAdmin: bool }"""

async def update_partner_status(request):
    """PUT /api/partners/{id}/status { status: "active"|"suspended" }"""

async def activate_partner(request):
    """POST /api/partners/activate"""
    # 由剛登入的被邀請者呼叫
    # 1. 驗證 Firebase ID token
    # 2. 用 email 查 partner doc
    # 3. 如果 status="invited" → 生成 apiKey, status="active"
    # 4. 回傳 partner data（含 apiKey）

admin_routes = [
    Route("/api/partners/invite", invite_partner, methods=["POST"]),
    Route("/api/partners/{id}/role", update_partner_role, methods=["PUT"]),
    Route("/api/partners/{id}/status", update_partner_status, methods=["PUT"]),
    Route("/api/partners/activate", activate_partner, methods=["POST"]),
]
```

#### C. Entrypoint 修改

```python
# tools.py entrypoint
from starlette.applications import Starlette
from starlette.routing import Mount
from zenos.interface.admin_api import admin_routes

app = Starlette(routes=[
    Mount("/api", routes=admin_routes),
    Mount("/", app=ApiKeyMiddleware(mcp.http_app(...))),
])
# ApiKeyMiddleware 只包 MCP，不包 /api（admin API 自行驗證 Firebase token）
```

### Dashboard 改動

#### A. Login 頁面擴充

```typescript
// login/page.tsx 新增 email link sign-in 處理
useEffect(() => {
  if (isSignInWithEmailLink(auth, window.location.href)) {
    let email = window.localStorage.getItem("emailForSignIn");
    if (!email) {
      email = window.prompt("請輸入你的 email 以完成登入");
    }
    signInWithEmailLink(auth, email, window.location.href)
      .then(() => router.push("/"));
  }
}, []);
```

#### B. AuthGuard 擴充

```typescript
// AuthGuard.tsx — 處理 invited 狀態
if (partner.status === "invited") {
  // 呼叫 /api/partners/activate 啟用帳號
  await fetch(`${API_URL}/api/partners/activate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  // 重新載入 partner data
}
if (partner.status === "suspended") {
  // 顯示「帳號已停用」錯誤
}
```

#### C. /team 頁面（新）

```
dashboard/src/app/team/page.tsx

組件：
- InviteForm: email input + invite button
- PartnerList: 表格顯示所有 partners
- PartnerActions: 角色切換 + 停用/啟用 dropdown

資料流：
- 讀取：直接 Firestore query（既有 read rules 可用）
- 寫入：透過 Cloud Run API（/api/partners/*）

Admin guard：非 admin 用戶 redirect 到首頁
```

#### D. AppNav 更新

Admin 用戶在導覽列看到「團隊」tab → `/team`

### Partner Schema 變更

```
partners/{docId}
  - email: string              # 不變
  - displayName: string        # invited 時 = email，登入後更新為 Google displayName
  - apiKey: string             # invited 時 = ""，activate 時生成 UUID
  - authorizedEntityIds: []    # 不變，目前未強制
  - isAdmin: boolean           # 不變
  - status: "invited" | "active" | "suspended"  # 新增 invited
  - invitedBy: string          # 新增：邀請者 email
  - createdAt: Timestamp
  - updatedAt: Timestamp
```

### 需要的環境設定

1. Firebase console 啟用 Email link (passwordless) sign-in provider
2. `firebase-admin` 已在 Python dependencies（用於 ID token 驗證）
3. Dashboard `.env` 不需改動（Firebase config 已有）

---

## 安全審查清單

- [x] Secrets：API key 在 Firestore，不進 log
- [x] Firestore rules：維持 `allow write: if false`，所有寫入走 Admin SDK
- [x] Admin 驗證：REST API 驗 Firebase ID token + 查 partner.isAdmin
- [x] 邀請濫用：只有 admin 能邀請（API 層驗證）
- [x] API key 生成：UUID v4，activate 時才生成（invited 階段無 key）
- [x] MCP Tool 無毀滅性操作：不變
