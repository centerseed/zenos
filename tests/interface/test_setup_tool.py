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


def _ok_data(result: dict) -> dict:
    assert result["status"] == "ok"
    return result["data"]


def _non_ok_data(result: dict, status: str = "rejected") -> dict:
    assert result["status"] == status
    return result["data"]


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
    (governance / "bootstrap-protocol.md").write_text("# Bootstrap Protocol\ncontent here", encoding="utf-8")
    (governance / "capture-governance.md").write_text("# Capture Governance\ncontent here", encoding="utf-8")
    (governance / "document-governance.md").write_text("# Document Governance\ncontent here", encoding="utf-8")
    (governance / "l2-knowledge-governance.md").write_text("# L2 Knowledge\ncontent here", encoding="utf-8")
    (governance / "shared-rules.md").write_text("# Shared Rules\ncontent here", encoding="utf-8")
    (governance / "task-governance.md").write_text("# Task Governance\ncontent here", encoding="utf-8")

    # workflow skills
    for name in ["knowledge-capture.md", "knowledge-sync.md", "setup.md", "governance-loop.md",
                  "feature.md", "debug.md", "triage.md"]:
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
        assert "skills/governance/bootstrap-protocol.md" in files
        assert "skills/governance/document-governance.md" in files
        assert "skills/governance/l2-knowledge-governance.md" in files
        assert "skills/governance/shared-rules.md" in files
        assert "skills/governance/task-governance.md" in files

    def test_full_selection_contains_all_workflow_skills(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("full")
        assert "skills/workflows/knowledge-capture.md" in files
        assert "skills/workflows/knowledge-sync.md" in files
        assert "skills/workflows/setup.md" in files
        assert "skills/workflows/governance-loop.md" in files

    def test_full_selection_returns_expected_file_count(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("full")
        assert len(files) == 13  # 6 governance + 7 workflow (agent roles optional, skipped when missing)

    def test_task_only_excludes_document_governance(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("task_only")
        assert "skills/governance/bootstrap-protocol.md" in files
        assert "skills/governance/document-governance.md" not in files
        assert "skills/governance/l2-knowledge-governance.md" not in files
        assert "skills/governance/shared-rules.md" in files
        assert "skills/governance/task-governance.md" in files

    def test_task_only_still_has_workflow_files(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("task_only")
        assert "skills/workflows/knowledge-capture.md" in files

    def test_doc_task_excludes_l2(self):
        from zenos.interface.setup_content import get_skill_files
        files = get_skill_files("doc_task")
        assert "skills/governance/bootstrap-protocol.md" in files
        assert "skills/governance/l2-knowledge-governance.md" not in files
        assert "skills/governance/document-governance.md" in files
        assert "skills/governance/shared-rules.md" in files
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
    def test_returns_all_registered_commands(self):
        from zenos.interface.setup_content import get_slash_commands
        cmds = get_slash_commands()
        assert len(cmds) == 12  # 4 zenos-* + 3 workflows + 5 marketing workflows

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
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        assert _ok_data(result)["action"] == "ask_platform"

    async def test_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        data = _ok_data(result)
        assert "bundle_version" in data
        assert isinstance(data["bundle_version"], str)
        assert len(data["bundle_version"]) > 0

    async def test_has_options_list(self):
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        data = _ok_data(result)
        assert "options" in data
        assert isinstance(data["options"], list)
        assert len(data["options"]) >= 3  # at least claude_code, claude_web, codex

    async def test_options_have_id_and_label(self):
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        for opt in _ok_data(result)["options"]:
            assert "id" in opt, "Each option must have 'id'"
            assert "label" in opt, "Each option must have 'label'"

    async def test_options_include_claude_code(self):
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        ids = [o["id"] for o in _ok_data(result)["options"]]
        assert "claude_code" in ids

    async def test_has_next_step_guidance(self):
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        assert "next_step" in _ok_data(result)


class TestSetupToolClaudeCode:
    """DC-2: setup(platform='claude_code') → manifest + slash_commands + claude_md_addition."""

    async def test_action_is_install(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        assert _ok_data(result)["action"] == "install"

    async def test_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        assert "bundle_version" in _ok_data(result)

    async def test_has_manifest(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "manifest" in data
        assert "skills" in data["manifest"]
        assert isinstance(data["manifest"]["skills"], list)

    async def test_payload_has_no_skill_files(self):
        """skill_files should no longer be in payload (avoids token limit)."""
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "skill_files" not in data["payload"]
        assert "skill_files" not in data

    async def test_payload_has_slash_commands(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "slash_commands" in data["payload"]
        assert len(data["payload"]["slash_commands"]) == 12

    async def test_payload_has_claude_md_addition(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "claude_md_addition" in data["payload"]
        assert len(data["payload"]["claude_md_addition"]) > 0

    async def test_has_installation_targets(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "installation_targets" in data
        assert len(data["installation_targets"]) == 2
        assert any(t["id"] == "current_directory" and t["recommended"] for t in data["installation_targets"])

    async def test_has_usage_summary(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "usage_summary" in data
        skills = [item["skill"] for item in data["usage_summary"]]
        assert "/zenos-setup" in skills
        assert "/zenos-sync" in skills

    async def test_instructions_contain_github_fetch(self):
        """Instructions must tell agent to fetch from GitHub."""
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        instructions_text = " ".join(_ok_data(result)["instructions"])
        assert "github" in instructions_text.lower() or "WebFetch" in instructions_text

    async def test_platform_field(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        assert _ok_data(result)["platform"] == "claude_code"


class TestSetupToolClaudeWeb:
    """DC-3: setup(platform='claude_web') → project_instructions + project_documents_tip."""

    async def test_action_is_install(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        assert _ok_data(result)["action"] == "install"

    async def test_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        assert "bundle_version" in _ok_data(result)

    async def test_payload_has_project_instructions(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        instructions = _ok_data(result)["payload"]["project_instructions"]
        assert isinstance(instructions, str)
        assert len(instructions) > 0

    async def test_project_instructions_contains_governance_loading_hint(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        instructions = _ok_data(result)["payload"]["project_instructions"]
        # Must contain references to the three governance capabilities
        assert "文件" in instructions or "document" in instructions.lower()
        assert "任務" in instructions or "task" in instructions.lower()
        assert "MCP-first" in instructions
        assert "read_source" in instructions
        assert "analyze" in instructions

    async def test_payload_has_project_documents_tip(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        payload = _ok_data(result)["payload"]
        assert "project_documents_tip" in payload
        assert len(payload["project_documents_tip"]) > 0

    async def test_has_fixed_project_instruction_target(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        data = _ok_data(result)
        assert "installation_targets" in data
        assert data["installation_targets"][0]["id"] == "project_instructions"
        assert data["installation_targets"][0]["recommended"] is True


class TestSetupToolCodex:
    """DC-4: setup(platform='codex') → manifest + agents_md_addition."""

    async def test_action_is_install(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        assert _ok_data(result)["action"] == "install"

    async def test_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        assert "bundle_version" in _ok_data(result)

    async def test_has_manifest(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        data = _ok_data(result)
        assert "manifest" in data
        assert "skills" in data["manifest"]

    async def test_payload_has_no_skill_files(self):
        """skill_files should no longer be in payload."""
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        data = _ok_data(result)
        assert "skill_files" not in data["payload"]
        assert "skill_files" not in data

    async def test_payload_has_agents_md_addition(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        data = _ok_data(result)
        assert "agents_md_addition" in data["payload"]
        assert len(data["payload"]["agents_md_addition"]) > 0

    async def test_has_installation_targets(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        data = _ok_data(result)
        assert "installation_targets" in data
        assert len(data["installation_targets"]) == 2
        assert any(t["id"] == "current_directory" and t["recommended"] for t in data["installation_targets"])

    async def test_has_usage_summary(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        data = _ok_data(result)
        assert "usage_summary" in data
        skills = [item["skill"] for item in data["usage_summary"]]
        assert "/zenos-capture" in skills
        assert "/zenos-governance" in skills

    async def test_instructions_contain_github_fetch(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        instructions_text = " ".join(_ok_data(result)["instructions"])
        assert "github" in instructions_text.lower() or "WebFetch" in instructions_text


class TestSetupToolUnsupportedPlatform:
    """DC-5: unsupported or 'other' platform → error response."""

    async def test_other_platform_returns_error(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="other")
        assert _non_ok_data(result)["error"] == "unsupported_platform"

    async def test_unknown_platform_returns_error(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="random_platform_xyz")
        assert _non_ok_data(result)["error"] == "unsupported_platform"

    async def test_error_response_has_supported_platforms(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="other")
        data = _non_ok_data(result)
        assert "supported_platforms" in data
        assert "claude_code" in data["supported_platforms"]

    async def test_error_response_has_bundle_version(self):
        """DC-6: even error response from unsupported_platform should have bundle_version."""
        from zenos.interface.mcp import setup
        result = await setup(platform="other")
        assert "bundle_version" in _non_ok_data(result)


class TestSetupToolBundleVersion:
    """DC-6: all successful responses include bundle_version."""

    async def test_ask_platform_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform=None)
        data = _ok_data(result)
        assert "bundle_version" in data
        assert data["bundle_version"] == "2.1.0"

    async def test_claude_code_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        data = _ok_data(result)
        assert "bundle_version" in data
        assert data["bundle_version"] == "2.1.0"

    async def test_claude_web_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web")
        assert "bundle_version" in _ok_data(result)

    async def test_codex_has_bundle_version(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex")
        assert "bundle_version" in _ok_data(result)


class TestSetupToolSkillSelection:
    """DC-7: skill_selection affects claude_md_addition governance lines."""

    async def test_task_only_claude_md_excludes_document_governance(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="task_only")
        claude_md = _ok_data(result)["payload"]["claude_md_addition"]
        assert "document-governance.md" not in claude_md
        assert "l2-knowledge-governance.md" not in claude_md

    async def test_task_only_claude_md_includes_task_governance(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="task_only")
        claude_md = _ok_data(result)["payload"]["claude_md_addition"]
        assert "task-governance.md" in claude_md

    async def test_doc_task_claude_md_excludes_l2(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="doc_task")
        claude_md = _ok_data(result)["payload"]["claude_md_addition"]
        assert "l2-knowledge-governance.md" not in claude_md
        assert "document-governance.md" in claude_md

    async def test_full_claude_md_includes_all_governance(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="full")
        claude_md = _ok_data(result)["payload"]["claude_md_addition"]
        assert "document-governance.md" in claude_md
        assert "l2-knowledge-governance.md" in claude_md
        assert "task-governance.md" in claude_md

    async def test_skill_selection_stored_in_response(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="task_only")
        assert _ok_data(result)["skill_selection"] == "task_only"


class TestSetupToolSkipOverview:
    """DC-8: skip_overview=True → no governance_overview field."""

    async def test_skip_overview_true_omits_field(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skip_overview=True)
        assert "governance_overview" not in _ok_data(result)

    async def test_skip_overview_false_includes_field(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skip_overview=False)
        data = _ok_data(result)
        assert "governance_overview" in data
        assert len(data["governance_overview"]) > 0

    async def test_default_includes_governance_overview(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code")
        assert "governance_overview" in _ok_data(result)

    async def test_skip_overview_applies_to_claude_web(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_web", skip_overview=True)
        assert "governance_overview" not in _ok_data(result)

    async def test_skip_overview_applies_to_codex(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex", skip_overview=True)
        assert "governance_overview" not in _ok_data(result)


class TestSetupManifestOnly:
    """Ticket 36c5afc2: Confirm mcp__zenos__setup returns manifest, not raw SKILL.md content."""

    async def test_claude_code_no_skill_files_in_response(self):
        """No skill_files key anywhere in the response dict."""
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skip_overview=True)
        data = _ok_data(result)
        assert "skill_files" not in data
        assert "skill_files" not in data.get("payload", {})

    async def test_codex_no_skill_files_in_response(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex", skip_overview=True)
        data = _ok_data(result)
        assert "skill_files" not in data
        assert "skill_files" not in data.get("payload", {})

    async def test_instructions_reference_github_raw_url(self):
        """Instructions must tell agent to fetch from GitHub raw URL, not inline."""
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skip_overview=True)
        instructions_text = " ".join(_ok_data(result)["instructions"])
        assert "raw.githubusercontent.com" in instructions_text

    async def test_manifest_skills_have_path_and_version_but_no_content(self):
        """Each skill entry in manifest has path and version but NOT content."""
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skip_overview=True)
        for skill in _ok_data(result)["manifest"]["skills"]:
            assert "path" in skill, f"Skill {skill.get('name')} missing 'path'"
            assert "version" in skill, f"Skill {skill.get('name')} missing 'version'"
            assert "content" not in skill, f"Skill {skill.get('name')} should not have 'content'"

    async def test_codex_manifest_skills_no_content(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="codex", skip_overview=True)
        for skill in _ok_data(result)["manifest"]["skills"]:
            assert "content" not in skill


class TestSetupToolInvalidSkillSelection:
    """DC-9: invalid skill_selection → error response."""

    async def test_invalid_selection_returns_error(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="invalid_value")
        assert _non_ok_data(result)["error"] == "invalid_skill_selection"

    async def test_error_has_message(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="xyz")
        data = _non_ok_data(result)
        assert "message" in data
        assert len(data["message"]) > 0

    async def test_invalid_selection_without_platform_still_errors(self):
        """skill_selection validation happens only when platform is given."""
        from zenos.interface.mcp import setup
        # Without platform → ask_platform (skill_selection not validated yet)
        result = await setup(platform=None, skill_selection="bad")
        assert _ok_data(result)["action"] == "ask_platform"

    async def test_empty_string_selection_returns_error(self):
        from zenos.interface.mcp import setup
        result = await setup(platform="claude_code", skill_selection="")
        assert _non_ok_data(result)["error"] == "invalid_skill_selection"
