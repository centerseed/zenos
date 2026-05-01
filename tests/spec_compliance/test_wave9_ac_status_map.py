"""Wave 9 AC status map guard.

This test keeps the PLAN-ontology-grand-refactor-wave9-migration E03/E03b
classification synchronized with the canonical task and MCP specs.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_SPEC = ROOT / "docs" / "specs" / "SPEC-task-governance.md"
MCP_SPEC = ROOT / "docs" / "specs" / "SPEC-mcp-tool-contract.md"


RUNTIME_ENFORCED = {
    "AC-TASK-01",
    "AC-TASK-02",
    "AC-TASK-03",
    "AC-TASK-04",
    "AC-TASK-05",
    "AC-TASK-06",
    "AC-TASK-07",
    "AC-TASK-08",
    "AC-TASK-08b",
    "AC-TASK-09",
    "AC-MCP-01",
    "AC-MCP-02",
    "AC-MCP-03",
    "AC-MCP-04",
    "AC-MCP-05",
    "AC-MCP-06",
    "AC-MCP-07",
    "AC-MCP-08",
    "AC-MCP-09",
    "AC-MCP-10",
    "AC-MCP-11",
    "AC-MCP-12",
    "AC-MCP-13",
    "AC-MCP-14",
    "AC-MCP-15",
    "AC-MCP-16",
    "AC-MCP-17",
    "AC-MCP-18",
    "AC-MCP-19",
    "AC-MCP-19a",
    "AC-MCP-19b",
    "AC-MCP-22",
    "AC-MCP-23",
    "AC-MCP-24",
    "AC-MCP-25",
    "AC-MCP-26",
    "AC-MCP-27",
    "AC-MCP-28",
    "AC-MCP-29",
    "AC-MCP-29a",
    "AC-MCP-30a",
    "AC-MCP-30b",
    "AC-MCP-30c",
    "AC-MCP-30d",
    "AC-MCP-32",
    "AC-MCP-32b",
    "AC-MCP-33",
    "AC-MCP-34",
    "AC-MCP-35",
}

GOVERNANCE_TARGET = {
    "AC-TASK-10",
    "AC-MCP-20",
    "AC-MCP-21",
    "AC-MCP-31",
}

PENDING_WAVE: set[str] = set()


def _spec_ac_ids() -> set[str]:
    text = TASK_SPEC.read_text(encoding="utf-8") + "\n" + MCP_SPEC.read_text(encoding="utf-8")
    return set(re.findall(r"\b(AC-(?:TASK|MCP)-[0-9]{2}[a-z]?)\b", text))


def test_wave9_ac_status_map_covers_all_task_and_mcp_contract_acs():
    documented = _spec_ac_ids()
    classified = RUNTIME_ENFORCED | GOVERNANCE_TARGET | PENDING_WAVE

    assert not (RUNTIME_ENFORCED & GOVERNANCE_TARGET)
    assert not (RUNTIME_ENFORCED & PENDING_WAVE)
    assert not (GOVERNANCE_TARGET & PENDING_WAVE)

    assert classified == documented


def test_wave9_ac_status_map_matches_plan_cutover_boundary():
    assert "AC-TASK-10" not in RUNTIME_ENFORCED
    assert {"AC-MCP-20", "AC-MCP-21", "AC-MCP-31"} <= GOVERNANCE_TARGET
    assert "AC-MCP-32" in RUNTIME_ENFORCED
    assert not PENDING_WAVE
