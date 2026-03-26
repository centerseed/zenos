from __future__ import annotations

import json
from pathlib import Path

import pytest

from zenos.skills_installer import (
    SkillInstallError,
    format_summary,
    install_skills,
    load_manifest,
    read_installed_version,
)


def _write_release(root: Path, *, version: str = "1.2.0") -> Path:
    skills_root = root / ".claude" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "skills": [
                    {
                        "name": "zenos-sync",
                        "version": version,
                        "path": "zenos-sync",
                        "files": ["SKILL.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    skill_dir = skills_root / "zenos-sync"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: zenos-sync\nversion: {version}\n---\n",
        encoding="utf-8",
    )
    return skills_root


def test_load_manifest_from_repo_root(tmp_path: Path) -> None:
    _write_release(tmp_path, version="2.0.1")

    manifest = load_manifest(str(tmp_path))

    assert manifest.source_type == "file"
    assert manifest.skills[0].name == "zenos-sync"
    assert manifest.skills[0].version == "2.0.1"


def test_install_skills_only_updates_outdated_versions(tmp_path: Path) -> None:
    _write_release(tmp_path, version="2.0.1")
    skills_dir = tmp_path / "installed"
    existing_dir = skills_dir / "zenos-sync"
    existing_dir.mkdir(parents=True)
    (existing_dir / "SKILL.md").write_text(
        "---\nname: zenos-sync\nversion: 2.0.0\n---\n",
        encoding="utf-8",
    )

    results = install_skills(skills_dir=skills_dir, source=str(tmp_path))

    assert len(results) == 1
    assert results[0].action == "updated"
    assert results[0].previous_version == "2.0.0"
    assert results[0].current_version == "2.0.1"
    assert read_installed_version(existing_dir) == "2.0.1"
    assert "updated 2.0.0 -> 2.0.1" in format_summary(results)


def test_install_skills_is_idempotent_for_current_version(tmp_path: Path) -> None:
    _write_release(tmp_path, version="2.0.1")
    skills_dir = tmp_path / "installed"
    current_dir = skills_dir / "zenos-sync"
    current_dir.mkdir(parents=True)
    (current_dir / "SKILL.md").write_text(
        "---\nname: zenos-sync\nversion: 2.0.1\n---\n",
        encoding="utf-8",
    )

    results = install_skills(skills_dir=skills_dir, source=str(tmp_path))

    assert results[0].action == "unchanged"
    assert read_installed_version(current_dir) == "2.0.1"


def test_install_skills_restores_previous_version_on_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_release(tmp_path, version="2.0.1")
    skills_dir = tmp_path / "installed"
    current_dir = skills_dir / "zenos-sync"
    current_dir.mkdir(parents=True)
    original_content = "---\nname: zenos-sync\nversion: 2.0.0\n---\n"
    (current_dir / "SKILL.md").write_text(original_content, encoding="utf-8")

    import zenos.skills_installer as installer

    real_replace = installer.os.replace
    calls = {"count": 0}

    def flaky_replace(src: str | Path, dst: str | Path) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("boom")
        real_replace(src, dst)

    monkeypatch.setattr(installer.os, "replace", flaky_replace)

    with pytest.raises(SkillInstallError):
        install_skills(skills_dir=skills_dir, source=str(tmp_path))

    assert (current_dir / "SKILL.md").read_text(encoding="utf-8") == original_content
