"""Setup tool 的平台 adapter。

每個 build_*_payload 函式接收 skill_selection 和 skip_overview，
回傳對應平台的完整 install response dict。
"""

from __future__ import annotations

from zenos.interface.setup_content import (
    get_bundle_version,
    get_manifest,
    get_packages,
    get_slash_commands,
)

# ──────────────────────────────────────────────
# Claude Web UI 精簡版 Project Instructions
# 約 800 中文字 / 1200 tokens，符合 1500 tokens 限制
# ──────────────────────────────────────────────

_CLAUDE_WEB_PROJECT_INSTRUCTIONS = """\
# ZenOS 治理模式

ZenOS 是公司的 AI Context 層：建一次 ontology（知識圖譜），每個 AI agent 都共享同一套 context，不用每次對話重新解釋公司背景。

## MCP-first 原則

ZenOS 的主接點是 MCP tools。skills 只用在 setup/capture/sync 這類批次流程，不是日常讀寫的必要條件。

## 你的 MCP Tools

- `search`：先找候選 context（entities/documents/tasks）
- `get`：拿單一項目的完整結構化資料
- `read_source`：只在需要原文時讀 source
- `write`：寫入/更新 ontology 草稿
- `confirm`：確認草稿或驗收 review 任務
- `task`：建票、更新狀態、交付結果
- `analyze`：掃治理品質與盲點

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
1. 任務必須 `linked_entities`——連結到 ontology 中的相關節點
2. 建立任務：`task(action="create", title="...", linked_entities=["entity-id"], plan_id="...", plan_order=1)`
3. 更新狀態：`task(action="update", id="task-id", status="in_progress")`
4. 查詢任務：`search(collection="tasks", status="todo,in_progress,review")`

## 最小使用慣例（10 行內）

1. 新任務先 `search`。
2. 命中後用 `get`。
3. 需要原文才 `read_source`。
4. 穩定知識才 `write`。
5. `write` 後視為 draft，正式生效走 `confirm`。
6. 後續執行事項用 `task`。
7. 任務進 `review` 前要填 `result`。
8. 任務最終完成走 `confirm(collection="tasks")`。
9. 週期性品質檢查用 `analyze`。
10. skills 只用於 setup/capture/sync 加速流程。

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
    "透過 ZenOS MCP setup tool 取得：呼叫 setup(platform='claude_web') 即可取得完整 skill 內容。"
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
    "接入原則：MCP-first、skill-thin。日常讀寫直接用 MCP tools，skills 只做 setup/capture/sync。"
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
        "> 若 `skills/governance/` 不存在，請先呼叫 `setup(platform='codex')`，再依 instructions 從 GitHub 下載並寫入 skills。"
    )


# ──────────────────────────────────────────────
# Platform adapters
# ──────────────────────────────────────────────

def _build_github_raw_base(manifest: dict) -> str:
    """從 manifest 取得 GitHub raw content base URL。"""
    repo = manifest.get("publisher", {}).get("repository", "https://github.com/centerseed/zenos")
    # 用 raw.githubusercontent.com 避免 GitHub /raw/ 的 302 redirect
    raw_repo = repo.replace("https://github.com/", "https://raw.githubusercontent.com/")
    return f"{raw_repo}/main"


def build_claude_code_payload(selection: str, skip_overview: bool) -> dict:
    """組裝 claude_code 平台的 install response。

    測試與既有 client contract 仍期待 manifest + slash_commands +
    claude_md_addition 的結構，因此這裡維持 install payload 形式，
    並用 instructions 指向 GitHub raw URL 下載最新 skill。
    """
    bundle_version = get_bundle_version()
    manifest = get_manifest()
    packages = get_packages()
    slash_commands = get_slash_commands()
    claude_md_addition = _build_claude_md_addition(selection)
    raw_base = _build_github_raw_base(manifest)

    response: dict = {
        "action": "install",
        "platform": "claude_code",
        "bundle_version": bundle_version,
        "skill_selection": selection,
        "manifest": manifest,
        "packages": packages,
        "payload": {
            "slash_commands": slash_commands,
            "claude_md_addition": claude_md_addition,
            "packages": packages,
        },
        "instructions": [
            (
                f"1. 從 GitHub 下載最新 skill：用 curl -sL "
                f"{raw_base}/skills/release/{{skill.path}}/SKILL.md 取得各角色 skill，"
                f"並用 {raw_base}/skills/workflows/*.md / skills/governance/*.md 安裝 workflow 與治理文件"
            ),
            "2. 將 payload.slash_commands 寫入 .claude/commands/ 對應檔案",
            "3. 把 payload.claude_md_addition 追加到專案根目錄 CLAUDE.md",
            "4. 完成後執行 /zenos-setup 啟動完整安裝流程",
        ],
        "next_step": "/zenos-setup",
    }

    if not skip_overview:
        response["governance_overview"] = _GOVERNANCE_OVERVIEW

    return response


def build_claude_web_payload(selection: str, skip_overview: bool) -> dict:
    """組裝 claude_web 平台的完整 install response。"""
    bundle_version = get_bundle_version()
    packages = get_packages()

    response: dict = {
        "action": "install",
        "platform": "claude_web",
        "bundle_version": bundle_version,
        "skill_selection": selection,
        "packages": packages,
        "payload": {
            "project_instructions": _CLAUDE_WEB_PROJECT_INSTRUCTIONS,
            "project_documents_tip": _PROJECT_DOCUMENTS_TIP,
            "packages": packages,
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
    """組裝 codex 平台的完整 install response。

    不再回傳 skill 檔案內容，改為回傳 manifest + GitHub 安裝指引。
    """
    bundle_version = get_bundle_version()
    manifest = get_manifest()
    packages = get_packages()
    agents_md_addition = _build_agents_md_addition(selection)
    raw_base = _build_github_raw_base(manifest)

    response: dict = {
        "action": "install",
        "platform": "codex",
        "bundle_version": bundle_version,
        "skill_selection": selection,
        "manifest": manifest,
        "packages": packages,
        "payload": {
            "agents_md_addition": agents_md_addition,
            "packages": packages,
        },
        "instructions": [
            (
                f"1. 從 GitHub 拉取最新 skills：對 manifest.skills 中每個 skill，"
                f"用 Bash 執行 curl -sL {raw_base}/skills/release/{{skill.path}}/SKILL.md 下載內容"
            ),
            (
                "2. 安裝 skill 文件（addon-aware merge）：\n"
                "   a. 對於 skills/governance/ 和 skills/workflows/ 下的文件：直接寫入（無 addon 機制）\n"
                "   b. 對於 skills/release/{role}/SKILL.md：\n"
                "      - 先確認 .codex/skills/{role}/SKILL.md 是否存在\n"
                "      - 若存在：讀取其內容，找 '<!-- ZENOS_ADDON_SECTION_START -->' 標記\n"
                "        - 找到標記 → 保留標記到檔案結尾的所有內容（addon section）\n"
                "        - 未找到 → 代表舊版薄殼，addon section 視為不存在\n"
                "      - 將新版 SKILL.md 的內容 + addon section 合併後寫入 .codex/skills/{role}/SKILL.md\n"
                "      - 若 .codex/skills/{role}/SKILL.md 不存在：直接寫入新版內容 + 標準 addon loading section（見下方模板）\n"
                "   c. 標準 addon loading section 模板：\n"
                "      ---\n"
                "      <!-- ZENOS_ADDON_SECTION_START -->\n"
                "      ## 專案 Addon Skills\n\n"
                "      若 `skills/addons/{role}/` 目錄存在，在開始任何任務前，\n"
                "      用 Read tool 讀取該目錄下所有 .md 文件，按各 addon 的 `trigger` 條件套用。\n\n"
                "      若 `skills/addons/all/` 目錄存在，也讀取其中所有文件。\n"
                "      <!-- ZENOS_ADDON_SECTION_END -->"
            ),
            "3. 在專案根目錄的 AGENTS.md 加入 payload.agents_md_addition 的內容",
            "4. 完成後呼叫 mcp__zenos__search(query='ZenOS', collection='entities') 驗證 MCP 連線",
        ],
        "verification_command": "mcp__zenos__search(query='ZenOS', collection='entities')",
    }

    if not skip_overview:
        response["governance_overview"] = _GOVERNANCE_OVERVIEW

    return response
