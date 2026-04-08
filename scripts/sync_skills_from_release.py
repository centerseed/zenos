#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = REPO_ROOT / "skills" / "release"
AGENTS_ROOT = REPO_ROOT / "skills" / "agents"
SKILLS = (
    # ZenOS platform skills
    "zenos-setup",
    "zenos-capture",
    "zenos-sync",
    "zenos-governance",
    # Agent role skills
    "architect",
    "designer",
    "developer",
    "marketing",
    "pm",
    "qa",
    "debugger",
    "challenger",
    "coach",
)


def sync_skills_to(target_root: Path) -> None:
    """Sync SSOT-managed files from release/ to target, preserving non-SSOT files (e.g. LOCAL.md).

    Only overwrites files that exist in the release source directory.
    Files in the target that are NOT in the release source are left untouched.
    """
    target_root.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        src = RELEASE_ROOT / name
        dst = target_root / name
        dst.mkdir(parents=True, exist_ok=True)
        for src_file in src.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(src)
                dst_file = dst / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
    # Sync manifest.json so version numbers stay in sync
    manifest_src = RELEASE_ROOT / "manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, target_root / "manifest.json")


def sync_agents_to(target_root: Path) -> int:
    """Sync skills/agents/*.md → .claude/agents/ (or .codex/agents/)."""
    if not AGENTS_ROOT.exists():
        return 0
    target_root.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in AGENTS_ROOT.glob("*.md"):
        shutil.copy2(src, target_root / src.name)
        count += 1
    return count


def sync_versions(project_root: Path) -> None:
    """Update .claude/zenos-versions.json from manifest.json so version tracking stays in sync."""
    manifest_path = RELEASE_ROOT / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    versions = {s["name"]: s["version"] for s in manifest.get("skills", [])}
    versions_path = project_root / ".claude" / "zenos-versions.json"
    versions_path.parent.mkdir(parents=True, exist_ok=True)
    versions_path.write_text(json.dumps(versions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    home = Path.home()
    sync_skills_to(home / ".claude" / "skills")
    sync_skills_to(home / ".codex" / "skills")
    n_agents = sync_agents_to(home / ".claude" / "agents")
    sync_agents_to(home / ".codex" / "agents")
    sync_versions(REPO_ROOT)
    print(f"Synced {len(SKILLS)} skills: skills/release -> ~/.claude/skills and ~/.codex/skills")
    if n_agents:
        print(f"Synced {n_agents} agents: skills/agents -> ~/.claude/agents and ~/.codex/agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
