# ZenOS

中小企業的 AI Context 層——建一次 ontology，所有 AI agent 共享同一套 context。
Semantic Proxy：不是 ERP、不是搜尋引擎、不是文件管理。Phase 0 → 開發中。

## Hard Constraints

1. **任務管理只用 ZenOS MCP task tools**（`mcp__zenos__task`）— 用其他工具會繞過 ontology 的 task tracking
2. **毀滅性操作不暴露為 MCP tool** — purge_all 只能用 admin script，防止 agent 誤觸資料全滅
3. **部署後必須實際驗證服務可用** — deploy 成功 ≠ 服務正常；curl / 瀏覽器確認端點回應
4. **MCP 交付用 partner key 做端到端驗證** — 確保走過 auth + data scope，不是只測 happy path
5. **智慧邏輯只放 server 端** — 不散到 caller skill / dashboard；邏輯分叉後無法統一修正
6. **UI 術語映射** — 不出現 entity/ontology。Product→專案、Module→模組、Knowledge Graph→知識地圖、Entity→節點

## Architecture

- DDD 四層：`domain → application → infrastructure → interface`（`src/zenos/`）
- MCP 入口：`src/zenos/interface/tools.py`
- Frontend：Next.js 15 + Tailwind（`dashboard/`）
- DB：PostgreSQL schema `zenos`（Cloud SQL `zentropy-4f7a5:asia-east1:zentropy-db`）
- Deploy：Frontend → Firebase Hosting / Backend → Cloud Run

## Commands

```bash
# Backend test（必須用 .venv，系統 Python 缺依賴）
.venv/bin/pytest tests/ -x

# Frontend test
cd dashboard && npx vitest run

# Deploy — 根據改動範圍選腳本，不手打指令
./scripts/deploy.sh          # dashboard (Firebase Hosting)
./scripts/deploy_mcp.sh      # Python backend (Cloud Run)
```

## Known Gotchas

- 部署 Dashboard 只需 `--only hosting` — Firestore rules 已不再使用
- `python -m zenos.interface.tools` 啟動本地 MCP server（開發除錯用）
- 新 session 需深入理解產品：讀 `docs/spec.md` Part 0–1, 4–5, 7；速查 `docs/reference/REF-glossary.md`
