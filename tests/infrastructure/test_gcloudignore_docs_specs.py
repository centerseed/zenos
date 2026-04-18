"""Bug repro: .gcloudignore must exempt docs/specs/*.md so server can read SPECs at runtime.

Before fix: .gcloudignore excluded docs/ and *.md without exempting docs/specs/*.md,
causing governance_ssot_audit to always report 7 missing_spec_file findings in Cloud Run.
After fix: !docs/specs/*.md exemption ensures SPEC files are bundled in the image.
"""
from pathlib import Path


def test_gcloudignore_exempts_docs_specs():
    content = Path(".gcloudignore").read_text(encoding="utf-8")
    assert "!docs/specs/*.md" in content, (
        ".gcloudignore must exempt docs/specs/*.md; otherwise governance_ssot_audit "
        "fails with missing_spec_file in Cloud Run runtime."
    )
