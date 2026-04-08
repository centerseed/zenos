from __future__ import annotations

from pathlib import Path


def test_workflow_setup_skill_no_longer_depends_on_setup_py():
    content = Path("skills/workflows/setup.md").read_text(encoding="utf-8")
    assert "setup.py --token" not in content
    assert "setup.py --update" not in content
    assert "下載 setup.py" not in content
    assert "zenos_hook.py" not in content
    assert "Hook 安裝" not in content
    assert ".claude/mcp.json" in content


def test_release_setup_skill_no_longer_depends_on_setup_py():
    content = Path("skills/release/zenos-setup/SKILL.md").read_text(encoding="utf-8")
    assert "setup.py --token" not in content
    assert "setup.py --update" not in content
    assert "下載 setup.py" not in content
    assert "zenos_hook.py" not in content
    assert "Hook 安裝" not in content
    assert ".claude/mcp.json" in content
