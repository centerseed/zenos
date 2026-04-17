from __future__ import annotations

from pathlib import Path

from zenos.application.knowledge import governance_ssot_audit as audit


def test_run_governance_ssot_audit_green(monkeypatch, tmp_path: Path):
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "skills/governance").mkdir(parents=True)
    (tmp_path / "skills/release/zenos-capture").mkdir(parents=True)

    (tmp_path / "docs/specs/SPEC-l2-entity-redefinition.md").write_text(
        "L2 Entity 三問 impacts\n",
        encoding="utf-8",
    )
    (tmp_path / "skills/governance/l2-knowledge-governance.md").write_text(
        "> SSOT: `governance_guide(topic=\"entity\", level=2)` via MCP.\n"
        "> Agents must call governance_guide before acting on rules.\n",
        encoding="utf-8",
    )
    (tmp_path / "skills/release/zenos-capture/SKILL.md").write_text(
        "short skill\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(audit, "TOPIC_SPECS", {
        "entity": {
            "specs": ["docs/specs/SPEC-l2-entity-redefinition.md"],
            "keywords": ["L2 Entity", "三問", "impacts"],
        }
    })
    monkeypatch.setattr(audit, "REFERENCE_ONLY_FILES", ["skills/governance/l2-knowledge-governance.md"])
    monkeypatch.setattr(audit, "GOVERNANCE_RULES", {
        "entity": {
            1: "L2 Entity 三問 impacts",
            2: "L2 Entity 三問 impacts",
            3: "L2 Entity 三問 impacts",
        }
    })

    result = audit.run_governance_ssot_audit(tmp_path)

    assert result["overall_level"] == "green"
    assert result["findings"] == []


def test_run_governance_ssot_audit_flags_missing_reference_header(monkeypatch, tmp_path: Path):
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "skills/governance").mkdir(parents=True)
    (tmp_path / "skills/release/zenos-capture").mkdir(parents=True)

    (tmp_path / "docs/specs/SPEC-l2-entity-redefinition.md").write_text(
        "L2 Entity 三問 impacts\n",
        encoding="utf-8",
    )
    (tmp_path / "skills/governance/l2-knowledge-governance.md").write_text(
        "# no header\n",
        encoding="utf-8",
    )
    (tmp_path / "skills/release/zenos-capture/SKILL.md").write_text(
        "short skill\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(audit, "TOPIC_SPECS", {
        "entity": {
            "specs": ["docs/specs/SPEC-l2-entity-redefinition.md"],
            "keywords": ["L2 Entity", "三問", "impacts"],
        }
    })
    monkeypatch.setattr(audit, "REFERENCE_ONLY_FILES", ["skills/governance/l2-knowledge-governance.md"])
    monkeypatch.setattr(audit, "GOVERNANCE_RULES", {
        "entity": {
            1: "L2 Entity 三問 impacts",
            2: "L2 Entity 三問 impacts",
            3: "L2 Entity 三問 impacts",
        }
    })

    result = audit.run_governance_ssot_audit(tmp_path)

    assert result["overall_level"] == "yellow"
    assert any(item["type"] == "reference_only_header_missing" for item in result["findings"])
