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
