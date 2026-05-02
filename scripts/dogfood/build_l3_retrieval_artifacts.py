"""
build_l3_retrieval_artifacts.py

Builds all machine-readable artifacts for one L3 graph retrieval dogfood run:
- producer.jsonl
- monitor.json
- verdict.json

This script intentionally does not execute MCP tools. It consumes the transcript
from a clean-room session that already ran the scenario, then performs slicing,
metric extraction, and verdict generation in one command.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")
SCRIPT_DIR = Path(__file__).resolve().parent


def _load_module(filename: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_l3_retrieval_artifacts(
    *,
    df_id: str,
    transcripts_dir: str | Path,
    session_file: str | None,
    since_text: str,
    token_budget: int,
    expected_calls: int = 3,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    artifact_mod = _load_module("build_iteration_artifacts.py", "build_iteration_artifacts")
    verdict_mod = _load_module("build_l3_retrieval_verdict.py", "build_l3_retrieval_verdict")

    artifact_result = artifact_mod.build_iteration_artifacts(
        df_id=df_id,
        transcripts_dir=transcripts_dir,
        session_file=session_file,
        since_text=since_text,
        expect_read_source_preview=True,
        out_root=out_root,
    )
    verdict_result = verdict_mod.build_l3_retrieval_verdict(
        df_id=df_id,
        monitor_json=artifact_result["monitor_path"],
        producer_jsonl=artifact_result["producer_path"],
        token_budget=token_budget,
        expected_calls=expected_calls,
        out_root=out_root,
    )

    return {
        "df_id": df_id,
        "producer_path": artifact_result["producer_path"],
        "monitor_path": artifact_result["monitor_path"],
        "verdict_path": verdict_result["out_path"],
        "session_file": artifact_result["session_file"],
        "since_text": since_text,
        "total_mcp_calls": artifact_result["total_mcp_calls"],
        "rejected_count": artifact_result["rejected_count"],
        "reject_rate": artifact_result["reject_rate"],
        "verdict": verdict_result["verdict"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build L3 retrieval dogfood artifacts and verdict in one command")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--transcripts-dir", required=True)
    parser.add_argument("--session-file", required=True)
    parser.add_argument("--since-text", required=True)
    parser.add_argument("--token-budget", type=int, required=True)
    parser.add_argument("--expected-calls", type=int, default=3)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    result = build_l3_retrieval_artifacts(
        df_id=args.df_id,
        transcripts_dir=args.transcripts_dir,
        session_file=args.session_file,
        since_text=args.since_text,
        token_budget=args.token_budget,
        expected_calls=args.expected_calls,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
