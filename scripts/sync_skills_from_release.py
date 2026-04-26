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
    # Shared workflow skills published from release/workflows/
    "workflows/feature",
    "workflows/debug",
    "workflows/triage",
    "workflows/brainstorm",
    "workflows/marketing-intel",
    "workflows/marketing-plan",
    "workflows/marketing-generate",
    "workflows/marketing-adapt",
    "workflows/marketing-publish",
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

PLATFORM_AGENT_FILES = (
    "zenos-setup",
    "zenos-capture",
    "zenos-sync",
    "zenos-governance",
)

WORKFLOW_ALIASES = {
    "workflows/feature": "feature",
    "workflows/debug": "debug",
    "workflows/triage": "triage",
    "workflows/brainstorm": "brainstorm",
}

HOST_VARIANT_FILES = {
    "architect": {
        "claude_code": "SKILL.md",
        "codex": "SKILL.codex.md",
    },
    "developer": {
        "claude_code": "SKILL.md",
        "codex": "SKILL.codex.md",
    },
    "qa": {
        "claude_code": "SKILL.md",
        "codex": "SKILL.codex.md",
    },
}

STALE_PATTERN_LABELS = {
    "journal_read(limit=20": "journal-first context loading is deprecated; use recent_updates/tasks/entities first",
    "每次捕獲完都寫": "capture journal writes must be gated by actual knowledge changes",
    "模式 A/B/C 完成後都要做": "capture journal writes must not be mandatory for every mode",
    "啟動時讀 journal": "role startup must not require journal as the primary context source",
    "啟動時讀日誌": "role startup must not require journal as the primary context source",
}


def _copy_skill_dir(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for src_file in src.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(src)
            if rel.name.startswith("SKILL.") and rel.name != "SKILL.md":
                continue
            dst_file = dst / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)


def assert_no_stale_patterns(*roots: Path) -> None:
    """Fail sync if published skill targets still contain deprecated instructions."""
    findings: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        files = [root] if root.is_file() else list(root.rglob("*.md"))
        for path in files:
            if not path.is_file():
                continue
            if path.name == "LOCAL.md":
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for needle, reason in STALE_PATTERN_LABELS.items():
                if needle in content:
                    findings.append(f"{path}: contains {needle!r} ({reason})")
    if findings:
        joined = "\n".join(findings)
        raise RuntimeError(f"stale skill instructions remain after sync:\n{joined}")


def sync_skills_to(target_root: Path, host: str = "claude_code") -> None:
    """Sync SSOT-managed files from release/ to target, preserving non-SSOT files (e.g. LOCAL.md).

    Only overwrites files that exist in the release source directory.
    Files in the target that are NOT in the release source are left untouched.
    """
    target_root.mkdir(parents=True, exist_ok=True)
    published_roots: list[Path] = []
    for name in SKILLS:
        src = RELEASE_ROOT / name
        dst = target_root / name
        _copy_skill_dir(src, dst)
        published_roots.append(dst)
        alias = WORKFLOW_ALIASES.get(name)
        if alias:
            alias_dst = target_root / alias
            _copy_skill_dir(src, alias_dst)
            published_roots.append(alias_dst)
        variant_name = HOST_VARIANT_FILES.get(name, {}).get(host)
        if variant_name:
            variant_src = src / variant_name
            if variant_src.exists():
                shutil.copy2(variant_src, dst / "SKILL.md")
                alias = WORKFLOW_ALIASES.get(name)
                if alias:
                    shutil.copy2(variant_src, target_root / alias / "SKILL.md")
    governance_src = RELEASE_ROOT / "governance"
    if governance_src.exists():
        governance_dst = target_root / "governance"
        _copy_skill_dir(governance_src, governance_dst)
        published_roots.append(governance_dst)
    # Sync manifest.json so version numbers stay in sync
    manifest_src = RELEASE_ROOT / "manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, target_root / "manifest.json")
    assert_no_stale_patterns(*published_roots)


def sync_agents_to(target_root: Path) -> int:
    """Sync release-managed agents to .claude/agents/ (or .codex/agents/)."""
    target_root.mkdir(parents=True, exist_ok=True)
    count = 0
    published_files: list[Path] = []
    if AGENTS_ROOT.exists():
        for src in AGENTS_ROOT.glob("*.md"):
            dst = target_root / src.name
            shutil.copy2(src, dst)
            published_files.append(dst)
            count += 1
    for name in PLATFORM_AGENT_FILES:
        src = RELEASE_ROOT / name / "SKILL.md"
        if src.exists():
            dst = target_root / f"{name}.md"
            shutil.copy2(src, dst)
            published_files.append(dst)
            count += 1
    assert_no_stale_patterns(*published_files)
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
    sync_skills_to(home / ".claude" / "skills", host="claude_code")
    sync_skills_to(home / ".codex" / "skills", host="codex")
    n_agents = sync_agents_to(home / ".claude" / "agents")
    sync_agents_to(home / ".codex" / "agents")
    sync_versions(REPO_ROOT)
    print(f"Synced {len(SKILLS)} skills: skills/release -> ~/.claude/skills and ~/.codex/skills")
    if n_agents:
        print(f"Synced {n_agents} agents: skills/agents -> ~/.claude/agents and ~/.codex/agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
