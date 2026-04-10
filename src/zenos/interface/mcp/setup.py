"""MCP tool: setup — install or update ZenOS setup skill."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_VALID_PLATFORMS = frozenset({"claude_code", "claude_web", "codex"})
_VALID_SKILL_SELECTIONS = frozenset({"full", "doc_task", "task_only"})


async def setup(
    platform: str | None = None,
    skill_selection: str = "full",
    skip_overview: bool = False,
) -> dict:
    """安裝或更新 ZenOS setup skill 到用戶的 AI agent 平台。

    用戶完成 MCP 連線後呼叫此 tool，取得安裝 setup skill 的 curl 指令。
    Claude 執行該指令後，再告知用戶執行 /zenos-setup 完成完整安裝。
    支援：Claude Code、Claude Web UI、OpenAI Codex / ChatGPT。

    使用時機：
    - 用戶說「安裝 ZenOS」「設定 ZenOS」「更新 ZenOS」→ setup(platform='claude_code')
    - tool 回傳 curl 指令 → Claude 執行 → 告知用戶執行 /zenos-setup

    不需要用這個工具的情境：
    - MCP 連線設定（取得 API key、填入 MCP server URL）→ 這是前置條件，不在 setup 範圍
    - 查詢 ontology → 用 search 或 get
    - 治理規則查詢 → 用 governance_guide

    Args:
        platform: 目標平台。claude_code / claude_web / codex（含 ChatGPT）。
                  不傳時回傳平台清單，讓 agent 詢問用戶後帶正確值再次呼叫。
        skill_selection: 治理能力組合（claude_code 平台已無作用，保留供其他平台使用）。
        skip_overview: 跳過治理概要說明，適合更新操作（已熟悉 ZenOS 的用戶）。

    Returns:
        platform=None → {"action": "ask_platform", "options": [...]}
        claude_code → {"action": "install_setup_skill", "command": "curl ...", "next_step": "/zenos-setup"}
        claude_web/codex → {"action": "install", "payload": {...}}
        platform invalid → {"error": "unsupported_platform"}
    """
    from zenos.interface.setup_content import get_bundle_version
    from zenos.interface.setup_adapters import (
        build_claude_code_payload,
        build_claude_web_payload,
        build_codex_payload,
    )

    # Step 1：無 platform → 回傳平台清單
    if platform is None:
        bundle_version = get_bundle_version()
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

    # Step 2：驗證 skill_selection
    if skill_selection not in _VALID_SKILL_SELECTIONS:
        return {
            "error": "invalid_skill_selection",
            "message": "skill_selection 必須是 full / doc_task / task_only",
        }

    # Step 3：依 platform 委派 adapter
    if platform == "claude_code":
        return build_claude_code_payload(skill_selection, skip_overview)
    if platform == "claude_web":
        return build_claude_web_payload(skill_selection, skip_overview)
    if platform == "codex":
        return build_codex_payload(skill_selection, skip_overview)

    # Step 4：不支援的平台
    bundle_version = get_bundle_version()
    return {
        "error": "unsupported_platform",
        "message": "目前不支援此平台，請聯繫 ZenOS 管理員或到 https://github.com/centerseed/zenos 查看最新文件",
        "supported_platforms": sorted(_VALID_PLATFORMS),
        "bundle_version": bundle_version,
    }
