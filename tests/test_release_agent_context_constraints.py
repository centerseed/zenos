from __future__ import annotations

from pathlib import Path


AGENT_SKILLS = [
    Path("skills/release/architect/SKILL.md"),
    Path("skills/release/developer/SKILL.md"),
    Path("skills/release/qa/SKILL.md"),
    Path("skills/release/pm/SKILL.md"),
    Path("skills/release/designer/SKILL.md"),
    Path("skills/release/marketing/SKILL.md"),
    Path("skills/release/debugger/SKILL.md"),
    Path("skills/release/challenger/SKILL.md"),
    Path("skills/release/coach/SKILL.md"),
]


def test_release_agent_skills_require_project_context_loading():
    for path in AGENT_SKILLS:
        content = path.read_text(encoding="utf-8")
        assert "LOCAL.md" in content, f"{path} should mention LOCAL.md loading"
        assert "mcp__zenos__journal_read" in content, f"{path} should require journal context loading"
