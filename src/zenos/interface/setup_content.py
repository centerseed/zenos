"""Setup tool 的 skill 內容載入器。

從 skills/ 目錄讀取 skill 文件，lru_cache 緩存。
Cloud Run instance 只在啟動後第一次呼叫時執行 I/O，後續 request 命中 cache。

路徑規則：
  開發環境：{repo_root}/skills/   (Path(__file__).parent * 4 levels up / skills)
  Cloud Run：/app/skills/          (Dockerfile COPY skills/ skills/ 後的位置)

兩者路徑相同，因為 WORKDIR /app 且 COPY src/ src/ 後 __file__ 為 /app/src/zenos/interface/setup_content.py，
四層 parent 正好回到 /app，再加 skills/ = /app/skills/。
"""

import json
from functools import lru_cache
from pathlib import Path

# 開發環境：<repo>/src/zenos/interface/setup_content.py → 4 parents up = <repo>
# Cloud Run：/app/src/zenos/interface/setup_content.py → 4 parents up = /app
_SKILLS_ROOT: Path = Path(__file__).parent.parent.parent.parent / "skills"

# governance skill 的選取清單（依 selection）
_GOVERNANCE_FILES: dict[str, list[str]] = {
    "full": ["document-governance.md", "l2-knowledge-governance.md", "task-governance.md"],
    "doc_task": ["document-governance.md", "task-governance.md"],
    "task_only": ["task-governance.md"],
}

# workflow skills（每個 selection 都包含）
_WORKFLOW_FILES: list[str] = [
    "knowledge-capture.md",
    "knowledge-sync.md",
    "setup.md",
    "governance-loop.md",
]

# slash command → SSOT skill 對應
_SLASH_COMMAND_SSOT: dict[str, str] = {
    "zenos-capture": "skills/workflows/knowledge-capture.md",
    "zenos-sync": "skills/workflows/knowledge-sync.md",
    "zenos-setup": "skills/workflows/setup.md",
    "zenos-governance": "skills/workflows/governance-loop.md",
}


@lru_cache(maxsize=None)
def get_manifest() -> dict:
    """讀取 skills/release/manifest.json，取得版本資訊。"""
    manifest_path = _SKILLS_ROOT / "release" / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def get_bundle_version() -> str:
    """從 manifest 取得目前 bundle 版本號（取所有 skill 中的最高版號）。"""
    manifest = get_manifest()
    versions = [s["version"] for s in manifest.get("skills", [])]
    if not versions:
        return "1.0.0"
    # 語意版本比較：轉成 tuple(int, int, int) 後取最大
    def _parse(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0, 0, 0)
    return max(versions, key=_parse)


@lru_cache(maxsize=None)
def _get_skill_files_cached(selection: str) -> dict[str, str]:
    """Internal cached loader — returns the canonical dict, do NOT mutate."""
    governance_files = _GOVERNANCE_FILES.get(selection, _GOVERNANCE_FILES["full"])

    result: dict[str, str] = {}
    for filename in governance_files:
        path = _SKILLS_ROOT / "governance" / filename
        result[f"skills/governance/{filename}"] = path.read_text(encoding="utf-8")
    for filename in _WORKFLOW_FILES:
        path = _SKILLS_ROOT / "workflows" / filename
        result[f"skills/workflows/{filename}"] = path.read_text(encoding="utf-8")
    return result


def get_skill_files(selection: str = "full") -> dict[str, str]:
    """回傳對應 skill_selection 的 skill 檔案內容 dict（每次回傳 copy，caller 可安全修改）。

    key = 相對路徑（如 'skills/governance/document-governance.md'）
    value = 檔案內容字串

    Args:
        selection: 必須是 VALID_SELECTIONS 中的值。

    Returns:
        Dict[path_str, file_content] 的淺層 copy。
    """
    return dict(_get_skill_files_cached(selection))


def get_slash_commands() -> dict[str, str]:
    """回傳 4 個 slash command 薄殼的內容 dict。

    key = 安裝路徑（如 '.claude/commands/zenos-capture.md'）
    value = markdown 薄殼內容（frontmatter + 指向 SSOT 的一行）
    """
    result: dict[str, str] = {}
    for name, ssot_path in _SLASH_COMMAND_SSOT.items():
        content = (
            f"---\n"
            f"description: ZenOS {name} — 自動安裝的治理 slash command\n"
            f"---\n\n"
            f"請閱讀並遵循 `{ssot_path}` 的完整指示執行。\n"
        )
        result[f".claude/commands/{name}.md"] = content
    return result
