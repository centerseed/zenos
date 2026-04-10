#!/usr/bin/env python3
"""One-shot import migration for ADR-026 module boundary refactor.

Rewrites all old flat import paths to new sub-package paths.
Run from repo root: python scripts/migrate_imports.py
"""

import re
import sys
from pathlib import Path

# ── Symbol → new module mapping ──────────────────────────────────

DOMAIN_MODELS_MAP = {
    # Knowledge Layer
    "Entity": "zenos.domain.knowledge",
    "Relationship": "zenos.domain.knowledge",
    "Document": "zenos.domain.knowledge",
    "DocumentTags": "zenos.domain.knowledge",
    "Source": "zenos.domain.knowledge",
    "Protocol": "zenos.domain.knowledge",
    "Gap": "zenos.domain.knowledge",
    "Tags": "zenos.domain.knowledge",
    "EntityEntry": "zenos.domain.knowledge",
    "Blindspot": "zenos.domain.knowledge",
    "EntityType": "zenos.domain.knowledge",
    "EntityStatus": "zenos.domain.knowledge",
    "RelationshipType": "zenos.domain.knowledge",
    "SourceType": "zenos.domain.knowledge",
    "DocumentStatus": "zenos.domain.knowledge",
    "EntryType": "zenos.domain.knowledge",
    "EntryStatus": "zenos.domain.knowledge",
    "Severity": "zenos.domain.knowledge",
    "BlindspotStatus": "zenos.domain.knowledge",
    # Action Layer
    "Task": "zenos.domain.action",
    "TaskStatus": "zenos.domain.action",
    "TaskPriority": "zenos.domain.action",
    # Identity Layer
    "UserPrincipal": "zenos.domain.identity",
    "AgentPrincipal": "zenos.domain.identity",
    "AgentScope": "zenos.domain.identity",
    "AccessPolicy": "zenos.domain.identity",
    "Visibility": "zenos.domain.identity",
    "Classification": "zenos.domain.identity",
    "InheritanceMode": "zenos.domain.identity",
    "VISIBILITY_ORDER": "zenos.domain.identity",
    "CLASSIFICATION_ORDER": "zenos.domain.identity",
    # Document Platform
    "DocRole": "zenos.domain.document_platform",
    "SourceStatus": "zenos.domain.document_platform",
    "DocStatus": "zenos.domain.document_platform",
    # Shared
    "SplitRecommendation": "zenos.domain.shared",
    "TagConfidence": "zenos.domain.shared",
    "StalenessWarning": "zenos.domain.shared",
    "QualityCheckItem": "zenos.domain.shared",
    "QualityReport": "zenos.domain.shared",
}

DOMAIN_REPOS_MAP = {
    "EntityRepository": "zenos.domain.knowledge",
    "RelationshipRepository": "zenos.domain.knowledge",
    "DocumentRepository": "zenos.domain.knowledge",
    "ProtocolRepository": "zenos.domain.knowledge",
    "BlindspotRepository": "zenos.domain.knowledge",
    "SourceAdapter": "zenos.domain.knowledge",
    "TaskRepository": "zenos.domain.action",
    "PartnerRepository": "zenos.domain.identity",
    # These stay in the old file (no sub-package yet)
    "ToolEventRepository": "zenos.domain.repositories",
    "UsageLogRepository": "zenos.domain.repositories",
    "CrmRepository": "zenos.domain.repositories",
}

INFRA_SQL_REPO_MAP = {
    "SqlEntityRepository": "zenos.infrastructure.knowledge",
    "SqlRelationshipRepository": "zenos.infrastructure.knowledge",
    "SqlDocumentRepository": "zenos.infrastructure.knowledge",
    "SqlProtocolRepository": "zenos.infrastructure.knowledge",
    "SqlBlindspotRepository": "zenos.infrastructure.knowledge",
    "SqlEntityEntryRepository": "zenos.infrastructure.knowledge",
    "SqlTaskRepository": "zenos.infrastructure.action",
    "PostgresTaskCommentRepository": "zenos.infrastructure.action",
    "SqlPartnerRepository": "zenos.infrastructure.identity",
    "SqlPartnerKeyValidator": "zenos.infrastructure.identity",
    "SqlToolEventRepository": "zenos.infrastructure.agent",
    "SqlUsageLogRepository": "zenos.infrastructure.agent",
    "SqlWorkJournalRepository": "zenos.infrastructure.agent",
    "SqlAuditEventRepository": "zenos.infrastructure.agent",
    # Shared helpers that moved to sql_common
    "get_pool": "zenos.infrastructure.sql_common",
    "_get_partner_id": "zenos.infrastructure.sql_common",
    "_acquire": "zenos.infrastructure.sql_common",
    "_acquire_with_tx": "zenos.infrastructure.sql_common",
    "_new_id": "zenos.infrastructure.sql_common",
    "_now": "zenos.infrastructure.sql_common",
    "_to_dt": "zenos.infrastructure.sql_common",
    "_json_loads_safe": "zenos.infrastructure.sql_common",
    "_dumps": "zenos.infrastructure.sql_common",
    "get_cached_health": "zenos.infrastructure.sql_common",
    "upsert_health_cache": "zenos.infrastructure.sql_common",
}

APP_MODULE_MAP = {
    "zenos.application.ontology_service": "zenos.application.knowledge.ontology_service",
    "zenos.application.source_service": "zenos.application.knowledge.source_service",
    "zenos.application.governance_service": "zenos.application.knowledge.governance_service",
    "zenos.application.governance_ai": "zenos.application.knowledge.governance_ai",
    "zenos.application.task_service": "zenos.application.action.task_service",
    "zenos.application.workspace_context": "zenos.application.identity.workspace_context",
    "zenos.application.permission_risk_service": "zenos.application.identity.permission_risk_service",
    "zenos.application.policy_suggestion_service": "zenos.application.identity.policy_suggestion_service",
    "zenos.application.crm_service": "zenos.application.crm.crm_service",
}

# ── Helper functions ─────────────────────────────────────────────

def parse_import_symbols(import_line: str) -> tuple[str, list[str]]:
    """Parse 'from X import A, B, C' → ('X', ['A', 'B', 'C'])."""
    m = re.match(r"from\s+([\w.]+)\s+import\s+\(?\s*", import_line)
    if not m:
        return "", []
    module = m.group(1)
    # Handle multi-line imports: collect everything after 'import'
    after_import = import_line[m.end():]
    # Remove trailing ) and comments
    after_import = re.sub(r"\)\s*$", "", after_import)
    after_import = re.sub(r"#.*", "", after_import)
    symbols = [s.strip().rstrip(",") for s in after_import.split(",") if s.strip().rstrip(",")]
    return module, symbols


def rewrite_domain_models_import(content: str) -> str:
    """Rewrite 'from zenos.domain.models import ...' to sub-package imports."""
    pattern = re.compile(
        r"^(\s*)from\s+zenos\.domain\.models\s+import\s+\(([^)]+)\)",
        re.MULTILINE | re.DOTALL,
    )

    def replacer(m):
        indent = m.group(1)
        body = m.group(2)
        symbols = [s.strip().rstrip(",") for s in re.split(r"[,\n]", body) if s.strip().rstrip(",")]
        return _build_grouped_imports(symbols, DOMAIN_MODELS_MAP, indent=indent)

    content = pattern.sub(replacer, content)

    # Single-line version (may be indented)
    pattern_single = re.compile(
        r"^(\s*)from\s+zenos\.domain\.models\s+import\s+(.+)$",
        re.MULTILINE,
    )

    def replacer_single(m):
        indent = m.group(1)
        body = m.group(2)
        symbols = [s.strip().rstrip(",") for s in body.split(",") if s.strip().rstrip(",")]
        return _build_grouped_imports(symbols, DOMAIN_MODELS_MAP, indent=indent)

    content = pattern_single.sub(replacer_single, content)
    return content


def rewrite_domain_repos_import(content: str) -> str:
    """Rewrite 'from zenos.domain.repositories import ...'."""
    pattern = re.compile(
        r"^(\s*)from\s+zenos\.domain\.repositories\s+import\s+\(([^)]+)\)",
        re.MULTILINE | re.DOTALL,
    )

    def replacer(m):
        indent = m.group(1)
        body = m.group(2)
        symbols = [s.strip().rstrip(",") for s in re.split(r"[,\n]", body) if s.strip().rstrip(",")]
        return _build_grouped_imports(symbols, DOMAIN_REPOS_MAP, indent=indent)

    content = pattern.sub(replacer, content)

    pattern_single = re.compile(
        r"^(\s*)from\s+zenos\.domain\.repositories\s+import\s+(.+)$",
        re.MULTILINE,
    )

    def replacer_single(m):
        indent = m.group(1)
        body = m.group(2)
        symbols = [s.strip().rstrip(",") for s in body.split(",") if s.strip().rstrip(",")]
        return _build_grouped_imports(symbols, DOMAIN_REPOS_MAP, indent=indent)

    content = pattern_single.sub(replacer_single, content)
    return content


def rewrite_infra_sql_repo_import(content: str) -> str:
    """Rewrite 'from zenos.infrastructure.sql_repo import ...'."""
    # Multi-line parenthesized imports (may be indented)
    pattern = re.compile(
        r"^(\s*)from\s+zenos\.infrastructure\.sql_repo\s+import\s+\(([^)]+)\)",
        re.MULTILINE | re.DOTALL,
    )

    def replacer(m):
        indent = m.group(1)
        body = m.group(2)
        symbols = [s.strip().rstrip(",") for s in re.split(r"[,\n]", body) if s.strip().rstrip(",")]
        return _build_grouped_imports(symbols, INFRA_SQL_REPO_MAP, indent=indent)

    content = pattern.sub(replacer, content)

    # Single-line imports (may be indented)
    pattern_single = re.compile(
        r"^(\s*)from\s+zenos\.infrastructure\.sql_repo\s+import\s+(.+)$",
        re.MULTILINE,
    )

    def replacer_single(m):
        indent = m.group(1)
        body = m.group(2)
        symbols = [s.strip().rstrip(",") for s in body.split(",") if s.strip().rstrip(",")]
        return _build_grouped_imports(symbols, INFRA_SQL_REPO_MAP, indent=indent)

    content = pattern_single.sub(replacer_single, content)
    return content


def rewrite_app_imports(content: str) -> str:
    """Rewrite 'from zenos.application.X import ...' to sub-package paths."""
    for old_mod, new_mod in APP_MODULE_MAP.items():
        content = content.replace(f"from {old_mod} import", f"from {new_mod} import")
    return content


def rewrite_tools_imports(content: str) -> str:
    """Rewrite 'from zenos.interface.mcp import ...' to mcp package."""
    content = content.replace(
        "from zenos.interface.mcp import",
        "from zenos.interface.mcp import",
    )
    return content


def _build_grouped_imports(symbols: list[str], mapping: dict[str, str], indent: str = "") -> str:
    """Group symbols by target module and build import lines."""
    groups: dict[str, list[str]] = {}
    unmapped = []
    for sym in symbols:
        if sym in mapping:
            mod = mapping[sym]
            groups.setdefault(mod, []).append(sym)
        else:
            unmapped.append(sym)

    lines = []
    for mod in sorted(groups.keys()):
        syms = sorted(groups[mod])
        if len(syms) == 1:
            lines.append(f"{indent}from {mod} import {syms[0]}")
        else:
            lines.append(f"{indent}from {mod} import {', '.join(syms)}")

    if unmapped:
        lines.append(f"{indent}# UNMAPPED: {', '.join(unmapped)}")

    return "\n".join(lines)


# Also handle relative imports within domain/ sub-packages
def rewrite_relative_domain_models(content: str, file_path: str) -> str:
    """For files inside domain/ sub-packages, rewrite relative imports from ..models."""
    if "/domain/knowledge/" in file_path:
        # Already handled by the sub-package structure
        pass
    elif "/domain/action/" in file_path:
        content = content.replace("from ..models import", "from zenos.domain.knowledge import")
    elif "/domain/identity/" in file_path:
        content = content.replace("from ..models import", "from zenos.domain.knowledge import")
    return content


# ── Main ─────────────────────────────────────────────────────────

SKIP_DIRS = {".venv", "node_modules", "__pycache__", ".git", ".claude", "dashboard"}
SKIP_FILES = {
    # Old files marked TO BE DELETED — skip them, they'll be deleted
    "src/zenos/domain/models.py",
    "src/zenos/domain/repositories.py",
    "src/zenos/infrastructure/sql_repo.py",
    "src/zenos/interface/tools.py",
    # Old flat application files — will be deleted
    "src/zenos/application/ontology_service.py",
    "src/zenos/application/source_service.py",
    "src/zenos/application/governance_service.py",
    "src/zenos/application/governance_ai.py",
    "src/zenos/application/task_service.py",
    "src/zenos/application/workspace_context.py",
    "src/zenos/application/permission_risk_service.py",
    "src/zenos/application/policy_suggestion_service.py",
    "src/zenos/application/crm_service.py",
    # ADR docs — don't rewrite examples
    "docs/decisions/ADR-026-module-boundary.md",
    "docs/decisions/ADR-027-layer-contract.md",
}


def should_process(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root))
    if rel in SKIP_FILES:
        return False
    for d in SKIP_DIRS:
        if f"/{d}/" in f"/{rel}" or rel.startswith(f"{d}/"):
            return False
    return path.suffix == ".py"


def migrate_file(path: Path, root: Path, dry_run: bool = False) -> bool:
    rel = str(path.relative_to(root))
    original = path.read_text()
    content = original

    content = rewrite_domain_models_import(content)
    content = rewrite_domain_repos_import(content)
    content = rewrite_infra_sql_repo_import(content)
    content = rewrite_app_imports(content)
    content = rewrite_tools_imports(content)

    if content != original:
        if dry_run:
            print(f"  WOULD CHANGE: {rel}")
        else:
            path.write_text(content)
            print(f"  CHANGED: {rel}")
        return True
    return False


def main():
    dry_run = "--dry-run" in sys.argv
    root = Path(__file__).resolve().parent.parent

    if dry_run:
        print("=== DRY RUN ===\n")

    changed = 0
    total = 0

    for py_file in sorted(root.rglob("*.py")):
        if should_process(py_file, root):
            total += 1
            if migrate_file(py_file, root, dry_run):
                changed += 1

    print(f"\n{'Would change' if dry_run else 'Changed'}: {changed}/{total} files")


if __name__ == "__main__":
    main()
