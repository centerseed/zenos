#!/usr/bin/env python3
"""Fail CI when governance SSOT layers drift."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from zenos.application.knowledge.governance_ssot_audit import run_governance_ssot_audit


def main() -> int:
    result = run_governance_ssot_audit()
    findings = result.get("findings", [])
    if findings:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print("governance_ssot lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
