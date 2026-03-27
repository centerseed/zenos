from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx


DEFAULT_MANIFEST_SOURCE = (
    "https://raw.githubusercontent.com/centerseed/zenos/main/"
    "skills/release/manifest.json"
)
VERSION_PATTERN = re.compile(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", re.MULTILINE)


class SkillInstallError(RuntimeError):
    """Raised when skill installation cannot safely complete."""


@dataclass(frozen=True)
class SkillRelease:
    name: str
    version: str
    path: str
    files: tuple[str, ...]
    owner: str | None = None


@dataclass(frozen=True)
class ReleaseManifest:
    source: str
    source_type: str
    source_root: str
    skills: tuple[SkillRelease, ...]


@dataclass(frozen=True)
class SkillInstallResult:
    name: str
    action: str
    previous_version: str | None
    current_version: str
    target_dir: Path


def parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise SkillInstallError(f"Invalid semantic version: {version}")
    return tuple(int(part) for part in parts)


def load_manifest(source: str = DEFAULT_MANIFEST_SOURCE) -> ReleaseManifest:
    manifest_source, source_type, source_root = _resolve_manifest_source(source)
    payload = json.loads(_read_text(manifest_source, source_type))
    skills: list[SkillRelease] = []
    for item in payload.get("skills", []):
        skills.append(
            SkillRelease(
                name=item["name"],
                version=item["version"],
                path=item["path"],
                files=tuple(item["files"]),
                owner=item.get("owner"),
            )
        )
    if not skills:
        raise SkillInstallError(f"No skills defined in manifest: {manifest_source}")
    for skill in skills:
        parse_semver(skill.version)
    return ReleaseManifest(
        source=manifest_source,
        source_type=source_type,
        source_root=source_root,
        skills=tuple(skills),
    )


def install_skills(
    *,
    skills_dir: str | Path,
    source: str = DEFAULT_MANIFEST_SOURCE,
) -> list[SkillInstallResult]:
    manifest = load_manifest(source)
    target_root = Path(skills_dir).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    results: list[SkillInstallResult] = []
    for release in manifest.skills:
        current_dir = target_root / release.name
        local_version = read_installed_version(current_dir)
        if local_version is not None and parse_semver(local_version) >= parse_semver(release.version):
            results.append(
                SkillInstallResult(
                    name=release.name,
                    action="unchanged",
                    previous_version=local_version,
                    current_version=local_version,
                    target_dir=current_dir,
                )
            )
            continue
        staged_dir = _stage_skill(manifest, release)
        _atomic_replace(staged_dir, current_dir)
        results.append(
            SkillInstallResult(
                name=release.name,
                action="installed" if local_version is None else "updated",
                previous_version=local_version,
                current_version=release.version,
                target_dir=current_dir,
            )
        )
    return results


def format_summary(results: list[SkillInstallResult]) -> str:
    lines = ["ZenOS skills setup summary:"]
    for result in results:
        if result.action == "unchanged":
            lines.append(f"- {result.name}: unchanged at {result.current_version}")
            continue
        previous = result.previous_version or "not-installed"
        lines.append(
            f"- {result.name}: {result.action} {previous} -> {result.current_version}"
        )
    return "\n".join(lines)


def read_installed_version(skill_dir: str | Path) -> str | None:
    skill_file = Path(skill_dir) / "SKILL.md"
    if not skill_file.exists():
        return None
    match = VERSION_PATTERN.search(skill_file.read_text(encoding="utf-8"))
    if match is None:
        return None
    version = match.group(1)
    parse_semver(version)
    return version


def _resolve_manifest_source(source: str) -> tuple[str, str, str]:
    if source.startswith(("http://", "https://")):
        manifest_source = source if source.endswith(".json") else f"{source.rstrip('/')}/manifest.json"
        source_root = manifest_source.rsplit("/", 1)[0] + "/"
        return manifest_source, "http", source_root

    expanded = Path(source).expanduser()
    if expanded.is_dir():
        manifest_path = expanded / "skills" / "release" / "manifest.json"
        if not manifest_path.exists():
            manifest_path = expanded / ".claude" / "skills" / "manifest.json"
        if not manifest_path.exists():
            manifest_path = expanded / "manifest.json"
    else:
        manifest_path = expanded

    if not manifest_path.exists():
        raise SkillInstallError(f"Manifest not found: {manifest_path}")

    return str(manifest_path.resolve()), "file", str(manifest_path.resolve().parent)


def _read_text(source: str, source_type: str) -> str:
    if source_type == "http":
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(source)
            response.raise_for_status()
            return response.text
    return Path(source).read_text(encoding="utf-8")


def _read_bytes(source: str, source_type: str) -> bytes:
    if source_type == "http":
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(source)
            response.raise_for_status()
            return response.content
    return Path(source).read_bytes()


def _stage_skill(manifest: ReleaseManifest, release: SkillRelease) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix=f"zenos-skill-{release.name}-"))
    staged_dir = temp_root / release.name
    staged_dir.mkdir(parents=True, exist_ok=True)
    try:
        for relative_file in release.files:
            source = _release_file_source(manifest, release, relative_file)
            destination = staged_dir / relative_file
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(_read_bytes(source, manifest.source_type))
        return staged_dir
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def _release_file_source(
    manifest: ReleaseManifest,
    release: SkillRelease,
    relative_file: str,
) -> str:
    release_path = f"{release.path.rstrip('/')}/{relative_file}"
    if manifest.source_type == "http":
        return urljoin(manifest.source_root, release_path)
    return str(Path(manifest.source_root) / release_path)


def _atomic_replace(staged_dir: Path, target_dir: Path) -> None:
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    backup_dir: Path | None = None
    try:
        if target_dir.exists():
            backup_dir = parent / f".{target_dir.name}.backup"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            os.replace(target_dir, backup_dir)
        os.replace(staged_dir, target_dir)
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir)
        staged_parent = staged_dir.parent
        if staged_parent.exists():
            shutil.rmtree(staged_parent, ignore_errors=True)
    except Exception as exc:
        if target_dir.exists() and not any(target_dir.iterdir()):
            shutil.rmtree(target_dir, ignore_errors=True)
        if backup_dir is not None and backup_dir.exists():
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            os.replace(backup_dir, target_dir)
        shutil.rmtree(staged_dir.parent, ignore_errors=True)
        raise SkillInstallError(
            f"Failed to install {target_dir.name}; previous version restored"
        ) from exc
