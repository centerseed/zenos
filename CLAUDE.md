# ZenOS

中小企業的 AI Context 層——建一次 ontology，公司的每一個 AI agent 都共享同一套 context。
不是 ERP、不是搜尋引擎、不是文件管理。是文件之上的語意代理（Semantic Proxy）。

## 階段

Phase 0 概念驗證 → 已進入開發。Backend: Python + PostgreSQL + MCP。Frontend: Next.js dashboard。

## 讀文件順序（新 session 必讀）

1. `docs/spec.md` Part 0–1（North Star + 核心命題）
2. `docs/spec.md` Part 4–5（Ontology 技術路線 + 漸進式信任）
3. `docs/spec.md` Part 7（服務架構 + Dashboard）

概念速查與關鍵發現見 `docs/reference/REF-glossary.md`。

## 技術棧

- Backend: Python 3.12, `src/zenos/`（DDD 四層：domain → application → infrastructure → interface）
- MCP Server: `src/zenos/interface/tools.py`（對外 MCP tools）
- Frontend: Next.js 15 + TypeScript + Tailwind, `dashboard/`
- DB: PostgreSQL（Cloud SQL `zentropy-4f7a5:asia-east1:zentropy-db`，schema `zenos`，12 tables）
- Deploy: Firebase Hosting（zenos-naruvia.web.app）+ Cloud Run
- Test: `pytest`（backend）, `vitest`（frontend）

## 開發規則

- 任務管理一律用 ZenOS MCP task tools（`mcp__zenos__task`），不用其他工具
- MCP 交付必須用 partner key 做端到端連線驗證
- 部署後必須實際驗證服務可用，不能只看 deploy 成功
- 部署 Dashboard 時只需部署 hosting（Firestore rules 已不再使用）
- 毀滅性操作（purge_all）絕不暴露為 MCP tool，只能用 admin script
- 智慧邏輯放在 ZenOS server 端，不散到 caller skill
- UI 不出現 entity/ontology 字眼。Product→專案、Module→模組、Knowledge Graph→知識地圖、Entity→「節點」

## 開發角色

角色 skill 定義在 `.claude/skills/`。Architect 用 subagent 調度 Developer/QA，不跳過 QA。

## 常用指令

```bash
# Backend（必須用 .venv，系統 Python 缺少依賴）
.venv/bin/pytest tests/ -x
python -m zenos.interface.tools  # 啟動 MCP server

# Frontend
cd dashboard && npm run dev
cd dashboard && npx vitest run

# Deploy
cd dashboard && npm run build && firebase deploy --only hosting
./scripts/deploy_mcp.sh
```

## ZenOS 治理技能

若當前專案有 `skills/governance/` 目錄（透過 `/zenos-setup` 安裝），
執行對應操作前**必須先用 Read tool 讀取該文件完整內容**再執行：

- 寫文件前讀：`skills/governance/document-governance.md`
- 建立 L2 概念前讀：`skills/governance/l2-knowledge-governance.md`
- 建立任務前讀：`skills/governance/task-governance.md`

> 若 `skills/governance/` 不存在，跳過治理流程。
