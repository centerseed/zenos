from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_sync_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "sync_skills_from_release.py"
    spec = importlib.util.spec_from_file_location("sync_skills_from_release", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sync_skills_preserves_local_md_and_installs_release_workflows(tmp_path: Path):
    mod = _load_sync_module()
    target = tmp_path / "skills"

    architect_dir = target / "architect"
    architect_dir.mkdir(parents=True)
    (architect_dir / "LOCAL.md").write_text("keep me\n", encoding="utf-8")

    mod.sync_skills_to(target)

    assert (target / "architect" / "LOCAL.md").read_text(encoding="utf-8") == "keep me\n"
    assert (target / "architect" / "SKILL.md").exists()
    assert (target / "workflows" / "feature" / "SKILL.md").exists()
    assert (target / "workflows" / "debug" / "SKILL.md").exists()
    assert (target / "workflows" / "triage" / "SKILL.md").exists()
    assert (target / "workflows" / "brainstorm" / "SKILL.md").exists()
    assert (target / "feature" / "SKILL.md").exists()
    assert (target / "debug" / "SKILL.md").exists()
    assert (target / "triage" / "SKILL.md").exists()
    assert (target / "brainstorm" / "SKILL.md").exists()
    assert (target / "workflows" / "marketing-intel" / "SKILL.md").exists()
    assert (target / "workflows" / "marketing-plan" / "SKILL.md").exists()
    assert (target / "workflows" / "marketing-generate" / "SKILL.md").exists()
    assert (target / "workflows" / "marketing-adapt" / "SKILL.md").exists()
    assert (target / "workflows" / "marketing-publish" / "SKILL.md").exists()
    assert (target / "governance" / "capture-governance.md").exists()


def test_sync_stale_check_ignores_preserved_local_md(tmp_path: Path):
    mod = _load_sync_module()
    target = tmp_path / "skills"

    architect_dir = target / "architect"
    architect_dir.mkdir(parents=True)
    (architect_dir / "LOCAL.md").write_text("啟動時讀 journal\n", encoding="utf-8")

    mod.sync_skills_to(target)

    assert (architect_dir / "LOCAL.md").read_text(encoding="utf-8") == "啟動時讀 journal\n"


def test_sync_agents_overwrites_legacy_platform_agents(tmp_path: Path):
    mod = _load_sync_module()
    target = tmp_path / "agents"
    target.mkdir(parents=True)
    (target / "zenos-capture.md").write_text(
        "old\njournal_read(limit=20, project=\"x\")\n",
        encoding="utf-8",
    )

    count = mod.sync_agents_to(target)

    assert count >= 4
    content = (target / "zenos-capture.md").read_text(encoding="utf-8")
    assert "journal_read(limit=20" not in content
    assert "SSOT: `governance_guide(topic=\"capture\", level=2)`" in content


def test_sync_fails_when_stale_instruction_survives(tmp_path: Path):
    mod = _load_sync_module()
    target = tmp_path / "published"
    target.mkdir()
    (target / "stale.md").write_text(
        "啟動時讀 journal\n",
        encoding="utf-8",
    )

    try:
        mod.assert_no_stale_patterns(target)
    except RuntimeError as exc:
        assert "stale skill instructions remain after sync" in str(exc)
        assert "啟動時讀 journal" in str(exc)
    else:
        raise AssertionError("expected stale instruction check to fail")


def test_context_happy_path_is_published_in_bootstrap_and_core_roles():
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "skills" / "release" / "governance" / "bootstrap-protocol.md",
        root / "skills" / "release" / "architect" / "SKILL.md",
        root / "skills" / "release" / "developer" / "SKILL.md",
        root / "skills" / "release" / "pm" / "SKILL.md",
        root / "skills" / "release" / "qa" / "SKILL.md",
    ]
    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert "Context Happy Path" in content
        assert "recent_updates" in content
        assert "L3 documents" in content or 'search(collection="documents"' in content
