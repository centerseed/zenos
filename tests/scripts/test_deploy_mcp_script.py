"""Tests for scripts/deploy_mcp.sh."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "deploy_mcp.sh"


def test_deploy_mcp_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_deploy_mcp_script_routes_target_revision_to_100_percent():
    text = SCRIPT.read_text()

    latest_created = "status.latestCreatedRevisionName"
    latest_ready = "status.latestReadyRevisionName"

    assert latest_created in text
    assert latest_ready in text
    assert text.index(latest_created) < text.index(latest_ready)
    assert 'if [ -z "$TARGET_REVISION" ]; then' in text
    assert "target revision: $TARGET_REVISION" in text
    assert "latest ready revision" not in text
    assert "gcloud run services update-traffic" in text
    assert '--to-revisions="${TARGET_REVISION}=100"' in text
    assert "_revision_has_100_percent_traffic" in text
    assert "serving revision: $TARGET_REVISION" in text


def test_deploy_mcp_script_uses_json_for_traffic_validation():
    text = SCRIPT.read_text()

    broken_csv_formatter = (
        "csv[no-heading](status.traffic.revisionName,"
        "status.traffic.percent,status.traffic.tag)"
    )

    assert broken_csv_formatter not in text
    assert "--format='json(status.traffic)'" in text
    assert "_service_traffic_json" in text
    assert "python3 -c" in text
    assert 'entry.get("revisionName") != expected_revision' in text
    assert "percent == 100" in text
    assert "_print_service_traffic" in text
    assert 'entry.get("tag", "")' in text
