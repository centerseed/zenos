---
type: TD
id: TD-agent-setup
status: Draft
ontology_entity: MCP 介面設計
created: 2026-03-29
updated: 2026-03-29
---

# Agent 自助安裝 — 技術設計

> 狀態：Draft
> 作者：Architect
> 交付對象：Developer
> 前置依賴：SPEC-agent-setup.md、現有 MCP 工具架構（tools.py）
> SPEC SSOT：`docs/specs/SPEC-agent-setup.md`

---

## 核心決策

### D1：跨平台 Skill 格式策略

**決策：一份 SSOT，三種交付 adapter。**

- `skills/governance/*.md` 和 `skills/workflows/*.md` 內容完全相同、不分平台
- 各平台的差異只在「如何打包這些內容讓 agent 能讀到」
- Server 的 `setup` tool 根據 `platform` 參數，選擇對應的 adapter 回傳

| 平台 | Adapter 邏輯 |
|------|-------------|
| `claude_code` | 回傳 skill 檔案內容 + CLAUDE.md 加入指示 + slash command entries |
| `claude_web` | 回傳可直接貼入 Project Instructions 的精簡文字（不含完整 skill 內容） |
| `codex` | 回傳 AGENTS.md 加入指示 + curl 指令（讓 agent 引導用戶下載 skills/） |

**為什麼不各自維護？**
維護三份平台特定內容需要每次更新三處，且格式漂移風險高。核心治理規則是文字，跨平台可讀。平台差異只在「指向路徑」和「設定檔位置」，不在規則內容本身。

**為什麼 Web UI 不內嵌完整 skill？**
Claude Web UI 的 Project Instructions 有大小限制，完整 3 個 governance skill 約 15k tokens，超限。改用精簡版（核心規則摘要，約 1.5k tokens）+ 建議上傳 skill 文件到 Project。

---

### D2：Server 端 Skill 內容儲存策略

**決策：Dockerfile 加入 `COPY skills/ skills/`，runtime 從 `/app/skills/` 讀取，用 `lru_cache` 緩存。**

- SSOT 維持在 `skills/` 目錄（不 hardcode 在 Python 模組中）
- Dockerfile 加一行 `COPY skills/ skills/`，讓 Cloud Run image 包含 skill 檔案
- `setup_content.py` 在 module import 時讀取並 cache，後續 request 不再 I/O
- 更新 skill 只需更新 `skills/` 下的 markdown 檔案 + 重新部署

**現況問題：** 目前 Dockerfile 只 COPY `src/`，`skills/` 不在 image 中。需要修改 Dockerfile。

---

### D3：版本號管理

**決策：沿用 `skills/release/manifest.json`，tool 從 manifest 讀取並回傳。**

- 版本號統一在 `skills/release/manifest.json` 的 `skills[].version` 欄位
- 新增 skill bundle 版本概念：manifest 頂層加 `bundle_version` 欄位，回傳給 caller
- 版本號語意：`major.minor.patch`（主要：架構變更，次要：新功能，patch：文字修正）
- Skill 更新流程：改 markdown → 改 manifest 版本號 → 重新部署

---

### D4：Tool 交互模型

**決策：一個 tool，兩步互動。**

1. `setup()` 無 platform → 回傳平台清單，提示 caller 再呼叫
2. `setup(platform="claude_code")` → 回傳完整安裝 payload

這樣讓 agent 可以在對話中詢問用戶後，用正確的 platform 參數再次呼叫，而不需要 tool 內部維護對話狀態。

---

## MCP Tool 介面定義

### Tool：`setup`

```python
async def setup(
    platform: str | None = None,
    skill_selection: str = "full",
    skip_overview: bool = False,
) -> dict:
```

**參數說明：**

| 參數 | 型別 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `platform` | `str \| None` | 否 | `None` | 目標平台。`None` 時回傳平台清單 |
| `skill_selection` | `str` | 否 | `"full"` | 治理能力組合。見下方選項 |
| `skip_overview` | `bool` | 否 | `False` | 跳過治理概要說明（P1，適合已熟悉 ZenOS 的更新操作） |

**`platform` 合法值：**

| 值 | 對應平台 |
|----|---------|
| `"claude_code"` | Claude Code（CLI 或 IDE 擴充套件） |
| `"claude_web"` | Claude Web UI（claude.ai 網頁版） |
| `"codex"` | OpenAI Codex 或 ChatGPT |

其他值 → 回傳 `error: "unsupported_platform"`。

**`skill_selection` 合法值：**

| 值 | 含義 |
|----|------|
| `"full"` | L2 知識治理 + L3 文件治理 + Task 治理 |
| `"doc_task"` | L3 文件治理 + Task 治理 |
| `"task_only"` | 僅 Task 治理 |

---

### 回傳格式

#### Case 1：`platform=None` → 詢問平台

```json
{
  "action": "ask_platform",
  "bundle_version": "2.1.0",
  "question": "你使用哪個 AI agent 平台？",
  "options": [
    {"id": "claude_code", "label": "Claude Code（CLI 或 IDE 擴充套件）"},
    {"id": "claude_web", "label": "Claude Web UI（claude.ai 網頁版）"},
    {"id": "codex", "label": "OpenAI Codex / ChatGPT"},
    {"id": "other", "label": "其他"}
  ],
  "next_step": "呼叫 setup(platform='<id>') 繼續安裝"
}
```

#### Case 2：`platform="claude_code"` → 完整安裝 payload

```json
{
  "action": "install",
  "platform": "claude_code",
  "bundle_version": "2.1.0",
  "skill_selection": "full",
  "payload": {
    "skill_files": {
      "skills/governance/document-governance.md": "<file_content>",
      "skills/governance/l2-knowledge-governance.md": "<file_content>",
      "skills/governance/task-governance.md": "<file_content>",
      "skills/workflows/knowledge-capture.md": "<file_content>",
      "skills/workflows/knowledge-sync.md": "<file_content>",
      "skills/workflows/setup.md": "<file_content>",
      "skills/workflows/governance-loop.md": "<file_content>"
    },
    "claude_md_addition": "## ZenOS 治理技能\n\n若當前專案有 `skills/governance/` 目錄...",
    "slash_commands": {
      ".claude/commands/zenos-capture.md": "---\ndescription: ...\n---\n...",
      ".claude/commands/zenos-sync.md": "...",
      ".claude/commands/zenos-setup.md": "...",
      ".claude/commands/zenos-governance.md": "..."
    }
  },
  "instructions": [
    "1. 將 payload.skill_files 中的每個 key 對應到專案根目錄的檔案路徑，寫入對應內容",
    "2. 在專案根目錄的 CLAUDE.md 加入 payload.claude_md_addition 的內容",
    "3. 將 payload.slash_commands 中每個 key-value 寫入對應路徑",
    "4. 完成後呼叫 mcp__zenos__search(query='ZenOS', collection='entities') 驗證 MCP 連線"
  ],
  "governance_overview": "...(若 skip_overview=false，包含一段約 200 字的治理概要說明)...",
  "verification_command": "mcp__zenos__search(query='ZenOS', collection='entities')"
}
```

#### Case 3：`platform="claude_web"` → Project Instructions payload

```json
{
  "action": "install",
  "platform": "claude_web",
  "bundle_version": "2.1.0",
  "payload": {
    "project_instructions": "...(精簡版 ZenOS 治理指示，約 1.5k tokens，可直接貼入 Project Instructions)...",
    "project_documents_tip": "建議將以下文件上傳到 Claude Project：\n- skills/governance/document-governance.md\n- skills/governance/l2-knowledge-governance.md\n- skills/governance/task-governance.md\n\n從 GitHub 下載：https://github.com/centerseed/zenos/tree/main/skills"
  },
  "instructions": [
    "1. 開啟 claude.ai → 進入你的 Project 設定",
    "2. 在 Project Instructions 貼入 payload.project_instructions 的內容",
    "3. （建議）依 payload.project_documents_tip 下載並上傳 skill 文件到 Project"
  ]
}
```

#### Case 4：`platform="codex"` → AGENTS.md payload

```json
{
  "action": "install",
  "platform": "codex",
  "bundle_version": "2.1.0",
  "payload": {
    "curl_command": "curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 \"zenos-main/skills/\"",
    "agents_md_addition": "## ZenOS 治理技能\n\n寫文件前讀：skills/governance/document-governance.md\n..."
  },
  "instructions": [
    "1. 在專案根目錄執行 payload.curl_command 下載 skills/",
    "2. 在 AGENTS.md 加入 payload.agents_md_addition 的內容"
  ]
}
```

#### Case 5：不支援的平台

```json
{
  "error": "unsupported_platform",
  "message": "目前不支援此平台，請聯繫 ZenOS 管理員或到 https://github.com/centerseed/zenos 查看最新文件"
}
```

---

## 實作架構

### 新增檔案

```
src/zenos/interface/
  setup_content.py    ← 讀取 skills/ 目錄，cache 內容
  setup_adapters.py   ← 三個平台的 payload 組裝邏輯
```

### 修改檔案

```
src/zenos/interface/tools.py   ← 加入 setup tool 定義
Dockerfile                      ← 加入 COPY skills/ skills/
```

---

### `setup_content.py` 設計

```python
"""Setup tool 的 skill 內容載入器。

從 /app/skills/ 讀取 skill 文件，lru_cache 緩存。
這樣 Cloud Run 每個 instance 只在啟動時讀一次 I/O。
"""
import json
from pathlib import Path
from functools import lru_cache

# Cloud Run 部署路徑：/app/skills/
# 本機開發路徑：{repo_root}/skills/
_SKILLS_ROOT = Path(__file__).parent.parent.parent.parent / "skills"


@lru_cache(maxsize=None)
def get_manifest() -> dict:
    """讀取 skills/release/manifest.json，取得版本資訊。"""
    manifest_path = _SKILLS_ROOT / "release" / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def get_bundle_version() -> str:
    """從 manifest 取得目前 bundle 版本號（取最高版號的 skill 版本）。"""
    manifest = get_manifest()
    versions = [s["version"] for s in manifest.get("skills", [])]
    return max(versions) if versions else "1.0.0"


@lru_cache(maxsize=None)
def get_skill_files(selection: str = "full") -> dict[str, str]:
    """回傳對應 skill_selection 的 skill 檔案內容 dict。

    key = 相對路徑（如 'skills/governance/document-governance.md'）
    value = 檔案內容字串
    """
    # 固定包含的 workflow skills（全選項都有）
    workflow_files = [
        "knowledge-capture.md",
        "knowledge-sync.md",
        "setup.md",
        "governance-loop.md",
    ]
    # 依 selection 決定包含哪些 governance skills
    governance_map = {
        "full": ["document-governance.md", "l2-knowledge-governance.md", "task-governance.md"],
        "doc_task": ["document-governance.md", "task-governance.md"],
        "task_only": ["task-governance.md"],
    }
    governance_files = governance_map.get(selection, governance_map["full"])

    result: dict[str, str] = {}
    for filename in governance_files:
        path = _SKILLS_ROOT / "governance" / filename
        result[f"skills/governance/{filename}"] = path.read_text(encoding="utf-8")
    for filename in workflow_files:
        path = _SKILLS_ROOT / "workflows" / filename
        result[f"skills/workflows/{filename}"] = path.read_text(encoding="utf-8")
    return result


@lru_cache(maxsize=None)
def get_slash_command_content(command_name: str) -> str:
    """讀取 slash command 的薄殼 SKILL.md 內容。

    薄殼只含 frontmatter + 一行指向 SSOT 的 include。
    """
    ssot_map = {
        "zenos-capture": "skills/workflows/knowledge-capture.md",
        "zenos-sync": "skills/workflows/knowledge-sync.md",
        "zenos-setup": "skills/workflows/setup.md",
        "zenos-governance": "skills/workflows/governance-loop.md",
    }
    ssot_path = ssot_map.get(command_name, "")
    return (
        f"---\n"
        f"description: ZenOS {command_name} — 由 setup tool 自動安裝\n"
        f"---\n\n"
        f"請閱讀並遵循 `{ssot_path}` 的完整指示執行。\n"
    )
```

---

### `setup_adapters.py` 設計

三個函式，各自組裝對應平台的 payload：

```python
def build_claude_code_payload(selection: str, skip_overview: bool) -> dict
def build_claude_web_payload(selection: str, skip_overview: bool) -> dict
def build_codex_payload(selection: str, skip_overview: bool) -> dict
```

`build_claude_code_payload` 主要工作：
1. 呼叫 `get_skill_files(selection)` 取得 skill 內容
2. 產生 CLAUDE.md 加入文字（依 selection 決定哪些 governance skill 要載入）
3. 產生 4 個 slash command 的薄殼內容（呼叫 `get_slash_command_content`）

`build_claude_web_payload` 主要工作：
1. 讀取精簡版 Project Instructions 模板（存在 `setup_content.py` 中的常數，約 1.5k tokens）
2. 附上下載 skill 文件的提示

`build_codex_payload` 主要工作：
1. 產生 curl 下載指令
2. 產生 AGENTS.md 加入文字

---

### Dockerfile 修改

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY skills/ skills/          # 新增
RUN pip install --no-cache-dir .

ENV PORT=8080
ENV MCP_TRANSPORT=sse

CMD ["python", "-m", "zenos.interface.mcp"]
```

---

### `tools.py` 加入 setup tool

```python
@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def setup(
    platform: str | None = None,
    skill_selection: str = "full",
    skip_overview: bool = False,
) -> dict:
    """自助安裝 ZenOS 治理能力到你的 AI agent 平台。

    已完成 MCP 連線的用戶呼叫此 tool，即可取得 ZenOS skill 安裝指引。
    支援：Claude Code、Claude Web UI、OpenAI Codex。

    使用時機：
    - 首次設定 ZenOS 治理能力 → setup()（不帶參數，取得平台清單）
    - 指定平台安裝 → setup(platform='claude_code')
    - 更新 skill 到最新版 → setup(platform='claude_code', skip_overview=True)
    - 只需要 Task 治理 → setup(platform='claude_code', skill_selection='task_only')

    不需要用這個工具的情境：
    - MCP 連線設定（取得 API key、填入 MCP server URL）→ 這是前置條件，不在 setup 範圍
    - 查詢 ontology → 用 search 或 get
    - 治理規則查詢 → 用 governance_guide

    Args:
        platform: 目標平台。claude_code / claude_web / codex。
                  不傳時回傳平台清單，讓 agent 詢問用戶後帶正確值再次呼叫。
        skill_selection: 治理能力組合。
                         full=完整（L2+L3+Task），doc_task=文件+Task，task_only=僅Task
        skip_overview: 跳過治理概要說明，適合更新操作（已熟悉 ZenOS 的用戶）
    """
    from zenos.interface.setup_content import get_bundle_version
    from zenos.interface.setup_adapters import (
        build_claude_code_payload,
        build_claude_web_payload,
        build_codex_payload,
    )

    bundle_version = get_bundle_version()

    if platform is None:
        return {
            "action": "ask_platform",
            "bundle_version": bundle_version,
            "question": "你使用哪個 AI agent 平台？",
            "options": [
                {"id": "claude_code", "label": "Claude Code（CLI 或 IDE 擴充套件）"},
                {"id": "claude_web", "label": "Claude Web UI（claude.ai 網頁版）"},
                {"id": "codex", "label": "OpenAI Codex / ChatGPT"},
                {"id": "other", "label": "其他"},
            ],
            "next_step": "呼叫 setup(platform='<id>') 繼續安裝",
        }

    if skill_selection not in ("full", "doc_task", "task_only"):
        return {
            "error": "invalid_skill_selection",
            "message": "skill_selection 必須是 full / doc_task / task_only",
        }

    if platform == "claude_code":
        return build_claude_code_payload(skill_selection, skip_overview)
    elif platform == "claude_web":
        return build_claude_web_payload(skill_selection, skip_overview)
    elif platform == "codex":
        return build_codex_payload(skill_selection, skip_overview)
    else:
        return {
            "error": "unsupported_platform",
            "message": "目前不支援此平台，請聯繫 ZenOS 管理員",
            "supported_platforms": ["claude_code", "claude_web", "codex"],
        }
```

---

## Spec 介面合約

| 介面 | 參數/行為 | Done Criteria 對應 |
|------|----------|--------------------|
| `setup(platform=None)` | 回傳 `action="ask_platform"` + 平台清單 | DC-1: 不帶 platform 時必須有 options 清單 |
| `setup(platform="claude_code")` | 回傳 `payload.skill_files` + `payload.slash_commands` | DC-2: claude_code payload 包含 skill 檔案內容 |
| `setup(platform="claude_web")` | 回傳 `payload.project_instructions` | DC-3: web payload 有可貼入的指示文字 |
| `setup(platform="codex")` | 回傳 `payload.curl_command` + `payload.agents_md_addition` | DC-4: codex payload 有 curl 指令 |
| `setup(platform="other")` | 回傳 `error="unsupported_platform"` | DC-5: 不支援平台有明確 error response |
| `bundle_version` 欄位 | 從 `manifest.json` 讀取，反映當前部署版本 | DC-6: 所有成功 response 都帶 bundle_version |
| `skill_selection` 過濾 | `full/doc_task/task_only` 控制回傳哪些 skill 檔案 | DC-7: task_only 時不回傳 document/l2 skill |
| `skip_overview=True` | 回傳 payload 不含 `governance_overview` 欄位 | DC-8: P1 功能，skip=true 時不輸出概要 |

---

## 風險與不確定性

### 我不確定的地方

- **Claude Web UI Project Instructions 大小限制**：目前設計回傳精簡版（約 1.5k tokens），但實際限制未驗證。若限制更低，需要進一步壓縮或改為 link-only 方式。
- **`skills/` 路徑解析**：`_SKILLS_ROOT = Path(__file__).parent.parent.parent.parent / "skills"` 在 Cloud Run 的解析正確性需要部署後驗證。若 Python module 安裝方式改變，相對路徑可能需要調整（可改用環境變數 `SKILLS_ROOT` 作為 fallback）。

### 可能的替代方案

- **governance_rules.py 模式（全 hardcode）**：不需修改 Dockerfile，但維護 skill 就要改兩個地方（markdown + Python 模組）。現有的 `governance_rules.py` 已有這個問題，不應繼續擴大。本設計選擇讀 filesystem 以維持 SSOT 一致性。
- **GitHub API 動態拉取**：每次 request 都從 GitHub 拉最新版。問題：增加延遲（GitHub API rate limit）且 staging/prod 無法控版本。不選。

### 需要用戶確認的決策

- **Claude Web UI 精簡版 Project Instructions 內容由誰寫？** 本 TD 設計由 Developer 寫一個合理的初始版本（包含三個 governance skill 的核心摘要），但最終內容需要 Barry 確認「夠不夠讓用戶知道 ZenOS 治理模式是什麼」。

### 最壞情況

若 `skills/` 路徑解析失敗，`setup` tool 會在 import 時 crash（`lru_cache` 在 import 時不執行，在首次呼叫時執行）。這會讓 setup tool 回傳 500，其他 tool 不受影響。修復只需修正路徑常數並重新部署，低風險。

---

## 實作任務拆分

### Developer 任務

**任務 D1：實作 setup_content.py + setup_adapters.py**
- 建立 `src/zenos/interface/setup_content.py`
- 建立 `src/zenos/interface/setup_adapters.py`（三個 platform adapter）
- 修改 `Dockerfile`（加入 `COPY skills/ skills/`）
- Done Criteria：
  - DC-6: `get_bundle_version()` 回傳 manifest.json 中最高版號
  - DC-2/3/4/7: 三個 adapter 各自組裝正確格式

**任務 D2：在 tools.py 加入 setup tool**
- 在 `tools.py` 加入 setup tool 定義
- Done Criteria：
  - DC-1 到 DC-8 全部通過
  - tool description 符合 MCP tool 設計原則（Purpose / When to use / Not to use）

**任務 D3：補齊 unit tests**
- `tests/test_setup_tool.py`
- 至少覆蓋：platform=None、四個平台（含 other）、skill_selection 過濾、skip_overview

### QA 任務

- 驗證 `setup(platform=None)` 回傳格式正確
- 驗證 `setup(platform="claude_code")` 包含所有必要 skill 文件
- 驗證 `setup(platform="claude_web")` 的 project_instructions 可讀（非空、包含治理載入指示）
- 驗證不支援平台回傳 error 格式
- 用 partner key 做端到端驗證（不是 superadmin key）
- 部署後確認 `/app/skills/` 路徑在 Cloud Run 中可正確讀取

---

## 預計影響範圍

**新增：**
- `src/zenos/interface/setup_content.py`
- `src/zenos/interface/setup_adapters.py`
- `tests/unit/test_setup_tool.py`
- `docs/designs/TD-agent-setup.md`（本文件）

**修改：**
- `src/zenos/interface/tools.py`（加入 setup tool）
- `Dockerfile`（加入 `COPY skills/ skills/`）

**不影響現有功能：**
- 現有 7 個 MCP tools 的行為不變
- `skills/` 目錄結構不變（只是 Docker image 中多一份 copy）
