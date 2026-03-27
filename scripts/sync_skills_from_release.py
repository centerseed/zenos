#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


RELEASE_ROOT = Path(__file__).resolve().parents[1] / "skills" / "release"
SKILLS = (
    "zenos-setup",
    "zenos-capture",
    "zenos-sync",
    "zenos-governance",
)


def sync_to(target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        src = RELEASE_ROOT / name
        dst = target_root / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def main() -> int:
    home = Path.home()
    sync_to(home / ".claude" / "skills")
    sync_to(home / ".codex" / "skills")
    print("Synced skills/release -> ~/.claude/skills and ~/.codex/skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
