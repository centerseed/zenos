"""Governance SSOT audit helpers shared by analyze and CI lint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zenos.interface.governance_rules import GOVERNANCE_RULES

REPO_ROOT = Path(__file__).resolve().parents[4]
REFERENCE_ONLY_MARKER = "SSOT: `governance_guide("
AGENT_RUNTIME_MARKER = "Agents must call governance_guide before acting on rules."
CAPTURE_SKILL_MAX_LINES = 200

TOPIC_SPECS: dict[str, dict[str, Any]] = {
    "entity": {
        "specs": ["docs/specs/SPEC-l2-entity-redefinition.md"],
        "keywords": ["L2 Entity", "三問", "impacts"],
    },
    "document": {
        "specs": ["docs/specs/SPEC-doc-governance.md"],
        "keywords": ["Frontmatter", "生命週期", "linked_entity_ids"],
    },
    "bundle": {
        "specs": ["docs/specs/SPEC-document-bundle.md"],
        "keywords": ["bundle-first", "doc_role=index", "bundle_highlights"],
    },
    "task": {
        "specs": ["docs/specs/SPEC-task-governance.md"],
        "keywords": ["Task", "linked_entities", "review"],
    },
    "capture": {
        "specs": [
            "docs/specs/SPEC-governance-guide-contract.md",
            "docs/specs/SPEC-l2-entity-redefinition.md",
        ],
        "keywords": ["分層路由", "三問", "impacts"],
    },
    "sync": {
        "specs": [
            "docs/specs/SPEC-document-bundle.md",
            "docs/specs/SPEC-doc-governance.md",
        ],
        "keywords": ["rename", "source_status", "bundle_highlights"],
    },
    "remediation": {
        "specs": ["docs/specs/SPEC-governance-feedback-loop.md"],
        "keywords": ["blindspot", "quality", "analyze"],
    },
}

REFERENCE_ONLY_FILES = [
    "skills/governance/bootstrap-protocol.md",
    "skills/governance/capture-governance.md",
    "skills/governance/document-governance.md",
    "skills/governance/l2-knowledge-governance.md",
    "skills/governance/shared-rules.md",
    "skills/governance/task-governance.md",
]


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_finding(
    *,
    severity: str,
    finding_type: str,
    message: str,
    topic: str | None = None,
    spec: str | None = None,
    file: str | None = None,
) -> dict:
    finding = {
        "severity": severity,
        "type": finding_type,
        "diff_summary": message,
    }
    if topic is not None:
        finding["topic"] = topic
    if spec is not None:
        finding["spec"] = spec
    if file is not None:
        finding["file"] = file
    return finding


def run_governance_ssot_audit(repo_root: Path | None = None) -> dict:
    """Compare server rules, specs, and reference skills for SSOT drift."""
    root = repo_root or REPO_ROOT
    findings: list[dict] = []

    for topic, config in TOPIC_SPECS.items():
        rules = GOVERNANCE_RULES.get(topic)
        if rules is None:
            findings.append(_build_finding(
                severity="red",
                finding_type="missing_server_topic",
                topic=topic,
                spec=", ".join(Path(spec).stem for spec in config["specs"]),
                message=f"governance_rules.py 缺少 topic '{topic}'。",
            ))
            continue
        missing_levels = [level for level in (1, 2, 3) if level not in rules]
        if missing_levels:
            findings.append(_build_finding(
                severity="red",
                finding_type="missing_server_level",
                topic=topic,
                spec=", ".join(Path(spec).stem for spec in config["specs"]),
                message=f"governance_rules.py topic '{topic}' 缺少 level {missing_levels}。",
            ))
            continue

        spec_text_parts: list[str] = []
        missing_specs: list[str] = []
        for spec_rel in config["specs"]:
            spec_path = root / spec_rel
            if not spec_path.exists():
                missing_specs.append(spec_rel)
                continue
            spec_text_parts.append(_load_text(spec_path))
        if missing_specs:
            findings.append(_build_finding(
                severity="red",
                finding_type="missing_spec_file",
                topic=topic,
                spec=", ".join(Path(spec).stem for spec in config["specs"]),
                message=f"找不到對應 spec：{', '.join(missing_specs)}",
            ))
            continue

        spec_text = _normalize("\n".join(spec_text_parts))
        rule_text = _normalize("\n".join(str(rules[level]) for level in (1, 2, 3)))
        missing_keywords = [
            keyword for keyword in config["keywords"]
            if _normalize(keyword) not in spec_text or _normalize(keyword) not in rule_text
        ]
        if missing_keywords:
            findings.append(_build_finding(
                severity="red",
                finding_type="spec_server_rules_drift",
                topic=topic,
                spec=", ".join(Path(spec).stem for spec in config["specs"]),
                message=f"缺少關鍵規則片段：{', '.join(missing_keywords)}",
            ))

    for rel_path in REFERENCE_ONLY_FILES:
        full_path = root / rel_path
        if not full_path.exists():
            findings.append(_build_finding(
                severity="yellow",
                finding_type="reference_file_missing",
                file=rel_path,
                message="reference-only 治理檔不存在。",
            ))
            continue
        content = _load_text(full_path)
        if REFERENCE_ONLY_MARKER not in content or AGENT_RUNTIME_MARKER not in content:
            findings.append(_build_finding(
                severity="yellow",
                finding_type="reference_only_header_missing",
                file=rel_path,
                message="缺少 reference-only header 或未明示先 call governance_guide。",
            ))

    capture_skill_path = root / "skills/release/zenos-capture/SKILL.md"
    if capture_skill_path.exists():
        line_count = len(_load_text(capture_skill_path).splitlines())
        if line_count > CAPTURE_SKILL_MAX_LINES:
            findings.append(_build_finding(
                severity="yellow",
                finding_type="capture_skill_too_long",
                file="skills/release/zenos-capture/SKILL.md",
                message=f"zenos-capture SKILL.md 行數 {line_count} > {CAPTURE_SKILL_MAX_LINES}",
            ))
    else:
        findings.append(_build_finding(
            severity="yellow",
            finding_type="capture_skill_missing",
            file="skills/release/zenos-capture/SKILL.md",
            message="找不到 zenos-capture release skill。",
        ))

    overall_level = "green"
    severities = {finding["severity"] for finding in findings}
    if "red" in severities:
        overall_level = "red"
    elif "yellow" in severities:
        overall_level = "yellow"

    return {
        "check_type": "governance_ssot",
        "findings": findings,
        "overall_level": overall_level,
    }
