"""Unit tests for the setup MCP tool.

Strategy:
- Mock _SKILLS_ROOT to a tmp_path with synthetic skill files so tests
  do not depend on the real skills/ directory.
- Mock setup_content.get_bundle_version / get_skill_files / get_slash_commands
  in adapters to keep adapter tests fast and isolated.
- Test the setup() tool handler directly by calling it as an async function.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────
# Fixtures: synthetic skills directory
# ──────────────────────────────────────────────

@pytest.fixture()
def skills_root(tmp_path: Path) -> Path:
    """Create a minimal skills/ directory structure for testing."""
    governance = tmp_path / "governance"
    workflows = tmp_path / "workflows"
    release = tmp_path / "release"
    governance.mkdir()
    workflows.mkdir()
    release.mkdir()

    # governance skills
    (governance / "capture-governance.md").write_text("# Capture Governance\ncontent here", encoding="utf-8")
    (governance / "document-governance.md").write_text("# Document Governance\ncontent here", encoding="utf-8")
    (governance / "l2-knowledge-governance.md").write_text("# L2 Knowledge\ncontent here", encoding="utf-8")
    (governance / "task-governance.md").write_text("# Task Governance\ncontent here", encoding="utf-8")

    # workflow skills
    for name in ["knowledge-capture.md", "knowledge-sync.md", "setup.md", "governance-loop.md"]:
        (workflows / name).write_text(f"# {name}\ncontent", encoding="utf-8")

    # manifest
    manifest = {
        "schema_version": 1,
        "skills": [
            {"name": "zenos-setup", "version": "1.0.0", "path": "zenos-setup", "files": ["SKILL.md"], "owner": "Barry"},
            {"name": "zenos-capture", "version": "2.1.0", "path": "zenos-capture", "files": ["SKILL.md"], "owner": "Barry"},
            {"name": "zenos-sync", "version": "2.0.1", "path": "zenos-sync", "files": ["SKILL.md"], "owner": "Barry"},
        ],
    }
    (release / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return tmp_path


@pytest.fixture(autouse=True)
def patch_skills_root(skills_root: Path):
    """Patch _SKILLS_ROOT in setup_content so all tests use the tmp skills dir."""
    # Must clear lru_cache between tests to avoid state leaking
    import zenos.interface.setup_content as sc

    # Clear caches before patching
    sc.resolve_skills_root.cache_clear()
    sc.get_manifest.cache_clear()
    sc.get_bundle_version.cache_clear()
    sc._get_skill_files_cached.cache_clear()

    with patch.object(sc, "_SKILLS_ROOT", skills_root):
        yield

    # Clear caches after test to avoid pollution
    sc.resolve_skills_root.cache_clear()
    sc.get_manifest.cache_clear()
    sc.get_bundle_version.cache_clear()
    sc._get_skill_files_cached.cache_clear()


# ──────────────────────────────────────────────
# setup_content unit tests
# ──────────────────────────────────────────────

class TestGetBundleVersion:
    def test_returns_highest_semantic_version(self):
        from zenos.interface.setup_content import get_bundle_version
        version = get_bundle_version()
        assert version == "2.1.0"  # highest among 1.0.0, 2.1.0, 2.0.1

    def test_returns_string(self):
        from zenos.interface.setup_content import get_bundle_version
        assert isinstance(get_bundle_version(), str)


class TestResolveSkillsRoot:
    def test_prefers_env_override(self, monkeypatch, tmp_path: Path):
        import zenos.interface.setup_content as sc

        custom_root = tmp_path / "custom-skills"
        release = custom_root / "release"
        governance = custom_root / "governance"
        workflows = custom_root / "workflows"
        release.mkdir(parents=True)
        governance.mkdir()
        workflows.mkdir()
        (release / "manifest.json").write_text('{"skills":[{"name":"zenos-setup","version":"1.0.0","path":"zenos-setup","files":["SKILL.md"]}]}', encoding="utf-8")

        monkeypatch.setenv("ZENOS_SKILLS_ROOT", str(custom_root))
        with patch.object(sc, "_SKILLS_ROOT", tmp_path / "missing-skills"):
            sc.resolve_skills_root.cache_clear()
            assert sc.resolve_skills_root() == custom_root.resolve()

    def test_falls_back_to_cwd_skills(self, monkeypatch, tmp_path: Path):
        import zenos.interface.setup_content as sc

        project_root = tmp_path / "project"
        skills = project_root / "skills"
        release = skills / "release"
        governance = skills / "governance"
        workflows = skills / "workflows"
        release.mkdir(parents=True)
        governance.mkdir()
        workflows.mkdir()
        (release / "manifest.json").write_text('{"skills":[{"name":"zenos-setup","version":"1.0.0","path":"zenos-setup","files":["SKILL.md"]}]}', encoding="utf-8")

        monkeypatch.delenv("ZENOS_SKILLS_ROOT", raising=False)
        monkeypatch.chdir(project_root)
        with patch.object(sc, "_SKILLS_ROOT", tmp_path / "missing-skills"):
            sc.resolve_skills_root.cache_clear()
            assert sc.resolve_skills_root() == skills.resolve()


class TestGetSkillFiles:
    def test_full_selection_contains_all_governance_skills(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("full")
        assert "skills/governance/document-governance.md" in files
        assert "skills/governance/l2-knowledge-governance.md" in files
        assert "skills/governance/task-governance.md" in files

    def test_full_selection_contains_all_workflow_skills(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("full")
        assert "skills/workflows/knowledge-capture.md" in files
        assert "skills/workflows/knowledge-sync.md" in files
        assert "skills/workflows/setup.md" in files
        assert "skills/workflows/governance-loop.md" in files

    def test_full_selection_returns_8_files(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("full")
        assert len(files) == 8

    def test_task_only_excludes_document_governance(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("task_only")
        assert "skills/governance/document-governance.md" not in files
        assert "skills/governance/l2-knowledge-governance.md" not in files
        assert "skills/governance/task-governance.md" in files

    def test_task_only_still_has_workflow_files(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("task_only")
        assert "skills/workflows/knowledge-capture.md" in files

    def test_doc_task_excludes_l2(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("doc_task")
        assert "skills/governance/l2-knowledge-governance.md" not in files
        assert "skills/governance/document-governance.md" in files
        assert "skills/governance/task-governance.md" in files

    def test_returns_copy_each_call(self):
        """Ensure returned dict is a new copy (not the lru_cache internal dict)."""
        from zenos.interface.setup_content import get_skill_files
        a = get_skill_files("full")
        b = get_skill_files("full")
        assert a is not b  # different dict objects

    def test_file_contents_are_non_empty_strings(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("full")
        for path, content in files.items():
            assert isinstance(content, str), f"{path} content should be str"
            assert len(content) > 0, f"{path} content should not be empty"


class TestGetSlashCommands:
    def test_returns_4_commands(self):
        from zenos.interface.setup_content import get_slash_commands
        cmds = get_slash_commands()
        assert len(cmds) == 4

    def test_all_paths_under_claude_commands(self):
        from zenos.interface.setup_content import get_slash_commands
        cmds = get_slash_commands()
        for path in cmds:
            assert path.startswith(".claude/commands/"), f"Unexpected path: {path}"
            assert path.endswith(".md")

    def test_each_command_has_description_frontmatter(self):
        from zenos.interface.setup_content import get_slash_commands
        cmds = get_slash_commands()
        for path, content in cmds.items():
            assert "description:" in content, f"{path} missing description frontmatter"

    def test_each_command_references_ssot_path(self):
        from zenos.interface.setup_content import get_slash_commands
        cmds = get_slash_commands()
        for path, content in cmds.items():
            assert "skills/" in content, f"{path} should reference SSOT path"


# ──────────────────────────────────────────────
# setup tool handler tests (via tools.setup())
# ──────────────────────────────────────────────

class TestSetupToolNoPlatform:
    """DC-1: setup(platform=None) → ask_platform response."""

    async def test_action_is_ask_platform(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        assert result["action"] == "ask_platform"

    async def test_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        assert "bundle_version" in result
        assert isinstance(result["bundle_version"], str)
        assert len(result["bundle_version"]) > 0

    async def test_has_options_list(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        assert "options" in result
        assert isinstance(result["options"], list)
        assert len(result["options"]) >= 3  # at least claude_code, claude_web, codex

    async def test_options_have_id_and_label(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        for opt in result["options"]:
            assert "id" in opt, "Each option must have 'id'"
            assert "label" in opt, "Each option must have 'label'"

    async def test_options_include_claude_code(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        ids = [o["id"] for o in result["options"]]
        assert "claude_code" in ids

    async def test_has_next_step_guidance(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        assert "next_step" in result


class TestSetupToolClaudeCode:
    """DC-2: setup(platform='claude_code') → skill_files + slash_commands + claude_md_addition."""

    async def test_action_is_install(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert result["action"] == "install"

    async def test_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert "bundle_version" in result

    async def test_payload_has_skill_files(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert "skill_files" in result["payload"]
        assert len(result["payload"]["skill_files"]) == 8

    async def test_payload_has_slash_commands(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert "slash_commands" in result["payload"]
        assert len(result["payload"]["slash_commands"]) == 4

    async def test_payload_has_claude_md_addition(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert "claude_md_addition" in result["payload"]
        assert len(result["payload"]["claude_md_addition"]) > 0

    async def test_platform_field(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert result["platform"] == "claude_code"


class TestSetupToolClaudeWeb:
    """DC-3: setup(platform='claude_web') → project_instructions + project_documents_tip."""

    async def test_action_is_install(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web")
        assert result["action"] == "install"

    async def test_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web")
        assert "bundle_version" in result

    async def test_payload_has_project_instructions(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web")
        instructions = result["payload"]["project_instructions"]
        assert isinstance(instructions, str)
        assert len(instructions) > 0

    async def test_project_instructions_contains_governance_loading_hint(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web")
        instructions = result["payload"]["project_instructions"]
        # Must contain references to the three governance capabilities
        assert "文件" in instructions or "document" in instructions.lower()
        assert "任務" in instructions or "task" in instructions.lower()

    async def test_payload_has_project_documents_tip(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web")
        assert "project_documents_tip" in result["payload"]
        assert len(result["payload"]["project_documents_tip"]) > 0


class TestSetupToolCodex:
    """DC-4: setup(platform='codex') → skill_files + agents_md_addition."""

    async def test_action_is_install(self):
        from zenos.interface.tools import setup
        result = await setup(platform="codex")
        assert result["action"] == "install"

    async def test_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform="codex")
        assert "bundle_version" in result

    async def test_payload_has_skill_files(self):
        from zenos.interface.tools import setup
        result = await setup(platform="codex")
        assert "skill_files" in result["payload"]
        assert len(result["payload"]["skill_files"]) > 0

    async def test_payload_has_agents_md_addition(self):
        from zenos.interface.tools import setup
        result = await setup(platform="codex")
        assert "agents_md_addition" in result["payload"]
        assert len(result["payload"]["agents_md_addition"]) > 0


class TestSetupToolUnsupportedPlatform:
    """DC-5: unsupported or 'other' platform → error response."""

    async def test_other_platform_returns_error(self):
        from zenos.interface.tools import setup
        result = await setup(platform="other")
        assert result["error"] == "unsupported_platform"

    async def test_unknown_platform_returns_error(self):
        from zenos.interface.tools import setup
        result = await setup(platform="random_platform_xyz")
        assert result["error"] == "unsupported_platform"

    async def test_error_response_has_supported_platforms(self):
        from zenos.interface.tools import setup
        result = await setup(platform="other")
        assert "supported_platforms" in result
        assert "claude_code" in result["supported_platforms"]

    async def test_error_response_has_bundle_version(self):
        """DC-6: even error response from unsupported_platform should have bundle_version."""
        from zenos.interface.tools import setup
        result = await setup(platform="other")
        assert "bundle_version" in result


class TestSetupToolBundleVersion:
    """DC-6: all successful responses include bundle_version."""

    async def test_ask_platform_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform=None)
        assert "bundle_version" in result
        assert result["bundle_version"] == "2.1.0"

    async def test_claude_code_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert "bundle_version" in result
        assert result["bundle_version"] == "2.1.0"

    async def test_claude_web_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web")
        assert "bundle_version" in result

    async def test_codex_has_bundle_version(self):
        from zenos.interface.tools import setup
        result = await setup(platform="codex")
        assert "bundle_version" in result


class TestSetupToolSkillSelection:
    """DC-7: skill_selection='task_only' excludes document and l2 governance skills."""

    async def test_task_only_excludes_document_governance(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="task_only")
        skill_files = result["payload"]["skill_files"]
        assert "skills/governance/document-governance.md" not in skill_files
        assert "skills/governance/l2-knowledge-governance.md" not in skill_files

    async def test_task_only_includes_task_governance(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="task_only")
        skill_files = result["payload"]["skill_files"]
        assert "skills/governance/task-governance.md" in skill_files

    async def test_doc_task_excludes_l2(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="doc_task")
        skill_files = result["payload"]["skill_files"]
        assert "skills/governance/l2-knowledge-governance.md" not in skill_files
        assert "skills/governance/document-governance.md" in skill_files

    async def test_full_includes_all_governance(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="full")
        skill_files = result["payload"]["skill_files"]
        assert "skills/governance/document-governance.md" in skill_files
        assert "skills/governance/l2-knowledge-governance.md" in skill_files
        assert "skills/governance/task-governance.md" in skill_files


class TestSetupToolSkipOverview:
    """DC-8: skip_overview=True → no governance_overview field."""

    async def test_skip_overview_true_omits_field(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skip_overview=True)
        assert "governance_overview" not in result

    async def test_skip_overview_false_includes_field(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skip_overview=False)
        assert "governance_overview" in result
        assert len(result["governance_overview"]) > 0

    async def test_default_includes_governance_overview(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code")
        assert "governance_overview" in result

    async def test_skip_overview_applies_to_claude_web(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_web", skip_overview=True)
        assert "governance_overview" not in result

    async def test_skip_overview_applies_to_codex(self):
        from zenos.interface.tools import setup
        result = await setup(platform="codex", skip_overview=True)
        assert "governance_overview" not in result


class TestSetupToolInvalidSkillSelection:
    """DC-9: invalid skill_selection → error response."""

    async def test_invalid_selection_returns_error(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="invalid_value")
        assert result["error"] == "invalid_skill_selection"

    async def test_error_has_message(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="xyz")
        assert "message" in result
        assert len(result["message"]) > 0

    async def test_invalid_selection_without_platform_still_errors(self):
        """skill_selection validation happens only when platform is given."""
        from zenos.interface.tools import setup
        # Without platform → ask_platform (skill_selection not validated yet)
        result = await setup(platform=None, skill_selection="bad")
        assert result["action"] == "ask_platform"

    async def test_empty_string_selection_returns_error(self):
        from zenos.interface.tools import setup
        result = await setup(platform="claude_code", skill_selection="")
        assert result["error"] == "invalid_skill_selection"
