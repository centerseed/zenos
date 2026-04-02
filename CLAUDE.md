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

治理規則的 SSOT 是 MCP server 端的 `governance_guide` tool。
執行治理相關操作前，呼叫對應 topic 取得最新規則：

| 操作場景 | 呼叫方式 |
|----------|---------|
| 寫文件（SPEC/ADR/TD 等） | `governance_guide(topic="document", level=2)` |
| 建立 L2 概念、寫 impacts | `governance_guide(topic="entity", level=2)` |
| 建立或驗收任務 | `governance_guide(topic="task", level=2)` |
| 知識捕獲（判斷分層） | `governance_guide(topic="capture", level=2)` |

> 若 MCP 不可用（未設定或連線失敗），跳過治理流程。
