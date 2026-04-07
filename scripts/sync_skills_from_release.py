#!/usr/bin/env python3
from __future__ import annotations

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
    target_root.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        src = RELEASE_ROOT / name
        dst = target_root / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
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


def main() -> int:
    home = Path.home()
    sync_skills_to(home / ".claude" / "skills")
    sync_skills_to(home / ".codex" / "skills")
    n_agents = sync_agents_to(home / ".claude" / "agents")
    sync_agents_to(home / ".codex" / "agents")
    print(f"Synced {len(SKILLS)} skills: skills/release -> ~/.claude/skills and ~/.codex/skills")
    if n_agents:
        print(f"Synced {n_agents} agents: skills/agents -> ~/.claude/agents and ~/.codex/agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
