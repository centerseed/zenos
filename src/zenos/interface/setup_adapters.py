"""Setup tool 的平台 adapter。

每個 build_*_payload 函式接收 skill_selection 和 skip_overview，
回傳對應平台的完整 install response dict。
"""

from __future__ import annotations

from zenos.interface.setup_content import (
    get_bundle_version,
    get_skill_files,
    get_slash_commands,
)

# ──────────────────────────────────────────────
# Claude Web UI 精簡版 Project Instructions
# 約 800 中文字 / 1200 tokens，符合 1500 tokens 限制
# ──────────────────────────────────────────────

_CLAUDE_WEB_PROJECT_INSTRUCTIONS = """\
# ZenOS 治理模式

ZenOS 是公司的 AI Context 層：建一次 ontology（知識圖譜），每個 AI agent 都共享同一套 context，不用每次對話重新解釋公司背景。

## 你的 MCP Tools

連線 ZenOS 後，你可以使用以下 tools：

- **search**：在 ontology 中搜尋節點、文件、任務。例：`search(query="產品路線圖", collection="entities")`
- **get**：取得指定節點的完整資料。例：`get(name="ZenOS")`
- **write**：新增或更新 ontology 節點（需 confirm 審核）。例：`write(name="新功能", entity_type="L3", summary="...")`
- **task**：建立、更新、查詢任務。例：`task(action="create", title="修 bug", linked_entity="ZenOS")`
- **confirm**：審核待確認的知識更新，接受或拒絕。例：`confirm(draft_id="xxx", action="accept")`

## 三個治理能力的觸發時機

### 文件治理（L3 Document Governance）
寫入或更新任何公司文件、知識節點時觸發：
1. 先用 `search` 確認此知識是否已存在
2. 確認後用 `write` 建立草稿
3. 用 `confirm` 審核後才正式入 ontology
4. 每份文件必須有 `source_uri`（指向原始檔案）

### L2 知識治理（L2 Concept Governance）
建立公司共識概念（跨部門共用的抽象名詞）時觸發：
1. L2 節點代表「公司共識概念」，例如「產品策略」「技術債」
2. 必須有 `impacts` 關聯——指向受影響的 L3 文件或專案
3. 用 `write(entity_type="L2", ...)` 建立

### 任務治理（Task Governance）
建立或更新工作任務時觸發：
1. 任務必須 `linked_entity`——連結到 ontology 中的相關節點
2. 建立任務：`task(action="create", title="...", linked_entity="節點名", plan_id="...", plan_order=1)`
3. 更新狀態：`task(action="update", task_id="...", status="in_progress")`
4. 查詢任務：`task(action="list", linked_entity="節點名")`

## 工作流程

開始任何工作前：
1. `search` 確認相關 context 已存在
2. 不存在才 `write` 建立
3. 建立任務時務必帶 `linked_entity`
4. 完成工作後更新任務狀態為 `done`

## 重要限制

- **不自動寫入**：除非用戶明確要求，不要主動 `write` 或建立任務
- **先讀後寫**：每次 `write` 前必須先 `search` 確認沒有重複
- **confirm 是必須的**：`write` 後產生的草稿必須經過 `confirm` 才正式生效
"""

_PROJECT_DOCUMENTS_TIP = (
    "建議將以下文件上傳到 Claude Project，讓 AI 在回答時能參考完整治理規則：\n"
    "- skills/governance/document-governance.md\n"
    "- skills/governance/l2-knowledge-governance.md\n"
    "- skills/governance/task-governance.md\n\n"
    "從 GitHub 下載：https://github.com/centerseed/zenos/tree/main/skills"
)

# ──────────────────────────────────────────────
# Governance overview（skip_overview=False 時附加）
# ──────────────────────────────────────────────

_GOVERNANCE_OVERVIEW = (
    "ZenOS 治理模式讓 AI agent 共享公司的知識結構（ontology），"
    "不再每次對話重新解釋背景。三層治理能力：\n"
    "① 文件治理（L3）——確保每份知識都有來源、版本、審核記錄\n"
    "② 概念治理（L2）——管理跨部門共用的抽象概念與影響關係\n"
    "③ 任務治理——讓工作任務連結到 ontology，AI 自動追蹤脈絡\n\n"
    "安裝完成後，在 Claude Code 的任何專案目錄中呼叫 ZenOS MCP tools 即可使用。"
)

# ──────────────────────────────────────────────
# CLAUDE.md 加入文字（依 selection 選擇要載入哪些 governance skill）
# ──────────────────────────────────────────────

_CLAUDE_MD_GOVERNANCE_LINES: dict[str, list[str]] = {
    "full": [
        "- 寫文件前讀：`skills/governance/document-governance.md`",
        "- 建立 L2 概念前讀：`skills/governance/l2-knowledge-governance.md`",
        "- 建立任務前讀：`skills/governance/task-governance.md`",
    ],
    "doc_task": [
        "- 寫文件前讀：`skills/governance/document-governance.md`",
        "- 建立任務前讀：`skills/governance/task-governance.md`",
    ],
    "task_only": [
        "- 建立任務前讀：`skills/governance/task-governance.md`",
    ],
}


def _build_claude_md_addition(selection: str) -> str:
    """組裝 CLAUDE.md 的 ZenOS 治理技能段落。"""
    lines = _CLAUDE_MD_GOVERNANCE_LINES.get(selection, _CLAUDE_MD_GOVERNANCE_LINES["full"])
    governance_block = "\n".join(lines)
    return (
        "## ZenOS 治理技能\n\n"
        "若當前專案有 `skills/governance/` 目錄（透過 `/zenos-setup` 安裝），\n"
        "執行對應操作前**必須先用 Read tool 讀取該文件完整內容**再執行：\n\n"
        f"{governance_block}\n\n"
        "> 若 `skills/governance/` 不存在，跳過治理流程。"
    )


def _build_agents_md_addition(selection: str) -> str:
    """組裝 AGENTS.md 的 ZenOS 治理技能段落。"""
    lines = _CLAUDE_MD_GOVERNANCE_LINES.get(selection, _CLAUDE_MD_GOVERNANCE_LINES["full"])
    governance_block = "\n".join(lines)
    return (
        "## ZenOS 治理技能\n\n"
        "執行對應操作前先讀取以下文件：\n\n"
        f"{governance_block}\n\n"
        "> 若 `skills/governance/` 不存在，請先執行 curl 指令下載 skills/。"
    )


# ──────────────────────────────────────────────
# Platform adapters
# ──────────────────────────────────────────────

def build_claude_code_payload(selection: str, skip_overview: bool) -> dict:
    """組裝 claude_code 平台的完整 install response。"""
    bundle_version = get_bundle_version()
    skill_files = get_skill_files(selection)
    slash_commands = get_slash_commands()
    claude_md_addition = _build_claude_md_addition(selection)

    response: dict = {
        "action": "install",
        "platform": "claude_code",
        "bundle_version": bundle_version,
        "skill_selection": selection,
        "payload": {
            "skill_files": skill_files,
            "claude_md_addition": claude_md_addition,
            "slash_commands": slash_commands,
        },
        "instructions": [
            "1. 將 payload.skill_files 中每個 key 作為專案根目錄的相對路徑，寫入對應內容",
            "2. 在專案根目錄的 CLAUDE.md 加入 payload.claude_md_addition 的內容",
            "3. 將 payload.slash_commands 中每個 key-value 寫入對應路徑（.claude/commands/）",
            "4. 完成後呼叫 mcp__zenos__search(query='ZenOS', collection='entities') 驗證 MCP 連線",
        ],
        "verification_command": "mcp__zenos__search(query='ZenOS', collection='entities')",
    }

    if not skip_overview:
        response["governance_overview"] = _GOVERNANCE_OVERVIEW

    return response


def build_claude_web_payload(selection: str, skip_overview: bool) -> dict:
    """組裝 claude_web 平台的完整 install response。"""
    bundle_version = get_bundle_version()

    response: dict = {
        "action": "install",
        "platform": "claude_web",
        "bundle_version": bundle_version,
        "skill_selection": selection,
        "payload": {
            "project_instructions": _CLAUDE_WEB_PROJECT_INSTRUCTIONS,
            "project_documents_tip": _PROJECT_DOCUMENTS_TIP,
        },
        "instructions": [
            "1. 開啟 claude.ai → 進入你的 Project 設定",
            "2. 在 Project Instructions 貼入 payload.project_instructions 的內容",
            "3. （建議）依 payload.project_documents_tip 下載並上傳 skill 文件到 Project",
        ],
    }

    if not skip_overview:
        response["governance_overview"] = _GOVERNANCE_OVERVIEW

    return response


def build_codex_payload(selection: str, skip_overview: bool) -> dict:
    """組裝 codex 平台的完整 install response。"""
    bundle_version = get_bundle_version()
    agents_md_addition = _build_agents_md_addition(selection)

    response: dict = {
        "action": "install",
        "platform": "codex",
        "bundle_version": bundle_version,
        "skill_selection": selection,
        "payload": {
            "curl_command": (
                "curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz"
                " | tar -xz --strip-components=1 \"zenos-main/skills/\""
            ),
            "agents_md_addition": agents_md_addition,
        },
        "instructions": [
            "1. 在專案根目錄執行 payload.curl_command 下載 skills/",
            "2. 在 AGENTS.md 加入 payload.agents_md_addition 的內容",
        ],
    }

    if not skip_overview:
        response["governance_overview"] = _GOVERNANCE_OVERVIEW

    return response
