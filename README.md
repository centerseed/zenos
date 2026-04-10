# ZenOS

ZenOS 是一個把「知識治理（Ontology）」和「行動治理（Task Action Layer）」連成閉環的 MCP 服務。

## 治理流程（先懂這個）

1. 用 `write` / `search` / `get` 維護 ontology（entities/documents/protocols/relationships/blindspots）。
2. 由 blindspot 或決策缺口建立 `task`（Action Layer）。
3. 任務交付後用 `confirm(collection="tasks", ...)` 驗收。
4. 驗收時把新知識回寫 ontology（必要時標記 stale 或新增 blindspot）。

要完整跑起來，通常需要三件事同時就位：
- ZenOS MCP server（能力底座）
- ZenOS skills（操作流程封裝）
- Agent client 的 MCP 設定（把工具接進工作流）

## 使用者側快速啟動（Skill + MCP）

### 1) 安裝並啟用 ZenOS skills

至少建議啟用：
- `zenos-setup`：初始化 MCP 連線與 token
- `zenos-capture`：把對話/檔案/專案寫入 ontology
- `zenos-sync`：依 git 變更做增量同步
- `zenos-governance`：治理總控（品質檢查、二次重整、task/confirm 閉環）

若你在 Codex / Claude 環境，直接觸發 `zenos-setup` 即可開始設定。

### 2) 把 ZenOS MCP 接進 client

在 client 的 MCP 設定中加入 `zenos` server（URL 請換成你的部署位址與 API key）：

```json
{
  "mcpServers": {
    "zenos": {
      "type": "http",
      "url": "https://<your-cloud-run>/mcp?api_key=<YOUR_API_KEY>"
    }
  }
}
```

本 repo 內已有範例設定檔：[.mcp.json](/Users/wubaizong/clients/ZenOS/.mcp.json)。

### 3) 連線驗證

連線後先呼叫：
- `search(collection="all", query="", limit=5)`

可正常返回資料即代表 MCP 已接通。

## Skill 更新（給使用者）

ZenOS skills 的官方發佈來源是 [`skills/release/manifest.json`](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json)，
安裝與升級入口統一為 `zenos-skills setup`。

### 1) 安裝 CLI 入口

在 repo 根目錄執行一次：

```bash
pip install -e .
```

之後就能從任何地方呼叫 `zenos-skills`。

### 2) 安裝或升級到全域 skills 目錄

```bash
zenos-skills setup --skills-dir ~/.codex/skills
```

這個命令會：

- 先讀中央 manifest，比對本地與遠端版本
- 只更新過期的 skill
- 輸出每個 skill 的名稱、舊版、新版與動作摘要
- 用原子替換保留舊版，若升級失敗會自動回滾

### 3) 從本 repo 本地測試發佈內容

若你在維護 ZenOS repo，想先用本地 manifest 驗證：

```bash
zenos-skills setup --source /Users/wubaizong/clients/ZenOS --skills-dir ~/.codex/skills
```

若要把同一份 release 同步到本機兩個 host 目錄（`.claude` + `.codex`）：

```bash
python /Users/wubaizong/clients/ZenOS/scripts/sync_skills_from_release.py
```

### 4) 實際升級範例

假設本地 `zenos-sync` 是 `2.0.0`，中央發佈版是 `2.0.1`，輸出會像這樣：

```text
ZenOS skills setup summary:
- zenos-setup: unchanged at 1.0.0
- zenos-capture: unchanged at 2.1.0
- zenos-sync: updated 2.0.0 -> 2.0.1
- zenos-governance: unchanged at 1.0.0
```

### 5) 故障排除

- 若看到 `Manifest not found`，請確認 `--source` 指向 repo 根目錄或 `manifest.json`。
- 若看到權限錯誤，檢查 `~/.codex/skills` 是否可寫。
- 若升級中斷，installer 會恢復舊版；可重新執行同一命令，不應產生重複安裝。

## 開發者本地啟動（MCP server）

### 1) 環境需求

- Python `>=3.11`
- PostgreSQL（`DATABASE_URL`）
- GitHub Token（讀 source adapter 用）

### 2) 安裝依賴

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3) 設定環境變數

可參考 [.env.example](/Users/wubaizong/clients/ZenOS/.env.example) 並至少補齊：

```bash
export DATABASE_URL='postgresql://<user>:<pass>@<host>:5432/<db>'
export GITHUB_TOKEN='<your_github_token>'
export MCP_TRANSPORT='stdio'   # 本地 client 直連建議用 stdio
```

### 4) 啟動 MCP server

```bash
python -m zenos.interface.mcp
```

SSE 模式（給 HTTP client）：

```bash
MCP_TRANSPORT=sse PORT=8080 python -m zenos.interface.mcp
```

## 部署

- Cloud Run MCP 部署腳本：[scripts/deploy_mcp.sh](/Users/wubaizong/clients/ZenOS/scripts/deploy_mcp.sh)
- 全站部署（測試 + dashboard + firebase）：[scripts/deploy.sh](/Users/wubaizong/clients/ZenOS/scripts/deploy.sh)

## SQL Migration（統一入口）

- Migration runner：[scripts/run_sql_migrations.py](/Users/wubaizong/clients/ZenOS/scripts/run_sql_migrations.py)
- 一鍵入口（自動讀 GCP secret `database-url`）：[scripts/migrate.sh](/Users/wubaizong/clients/ZenOS/scripts/migrate.sh)

常用指令：

```bash
# 看目前狀態（已套用 / 待套用）
./scripts/migrate.sh --status

# 只看待套用，不實際執行
./scripts/migrate.sh --dry-run

# 正式套用全部待套用 migration
./scripts/migrate.sh
```

備註：
- migration 版本紀錄會寫在 `zenos.schema_migrations`
- 若歷史環境已手動套過 SQL，但沒留下版本紀錄，runner 會在「物件已存在」時自動標記為已套用

## 最小可用流程（建議）

1. 先用 `zenos-setup` 接上 MCP。
2. 用 `zenos-capture` 把當前專案知識灌入 ontology。
3. 用 `search` / `analyze` 找治理缺口。
4. 用 `task` 建立行動項並執行。
5. 用 `confirm` 驗收並回寫知識閉環。
