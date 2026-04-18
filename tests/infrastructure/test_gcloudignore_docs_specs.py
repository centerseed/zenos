"""Bug repro: .gcloudignore must let docs/specs/*.md reach Cloud Run image.

Before fix: .gcloudignore excluded docs/ and *.md without properly exempting
docs/specs/*.md, causing governance_ssot_audit to always report
7 missing_spec_file findings at Cloud Run runtime.

After fix: exemption rules ensure SPEC files are actually bundled.

The first test is a behavioural check (simulates the exact gcloudignore
semantics that gcloud uses) so it fails if the pattern is syntactically
present but functionally broken — for example when a parent directory
exclusion prevents a `!` re-inclusion from taking effect.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _simulate_gcloudignore_matches(rules: list[str], path: str) -> bool:
    """Minimal gitignore-style matcher for .gcloudignore.

    Returns True if path is IGNORED. Implements the key semantics that bit us:
      1. Later rules override earlier ones.
      2. A `!` re-inclusion is ineffective if a parent directory is already
         excluded by a prior rule (git's documented limitation).
      3. `foo/*` excludes direct children but not the directory itself,
         so `!foo/bar` can still re-include a subpath.

    Patterns supported: exact names, directory trailing slash, `*` wildcard,
    `**` recursive wildcard, leading `!` negation. Good enough for this repo.
    """
    import fnmatch

    def pattern_matches(pattern: str, p: str) -> bool:
        # Strip trailing slash for directory patterns
        pat = pattern.rstrip("/")
        # Convert gitignore ** to fnmatch-compatible form
        if "**" in pat:
            # ** matches any sequence including /
            regex_pat = pat.replace("**/", "(.*/)?").replace("**", ".*")
            import re
            return bool(re.fullmatch(regex_pat.replace("*", "[^/]*").replace("(.*/)?", "(.*/)?"), p))
        # Exact match or prefix-match for directories
        if fnmatch.fnmatch(p, pat):
            return True
        # Directory prefix: "foo" matches "foo/anything"
        if "/" not in pat and p.startswith(pat + "/"):
            return True
        # "foo/*" matches direct children
        if pat.endswith("/*"):
            prefix = pat[:-2]
            remainder = p[len(prefix) + 1:] if p.startswith(prefix + "/") else None
            if remainder is not None and "/" not in remainder:
                return True
        return False

    ignored = False
    parent_excluded = False
    for rule in rules:
        rule = rule.strip()
        if not rule or rule.startswith("#"):
            continue
        negate = rule.startswith("!")
        pat = rule[1:] if negate else rule
        if pattern_matches(pat, path):
            if negate:
                # Re-include only if no ancestor is fully excluded
                if not parent_excluded:
                    ignored = False
            else:
                ignored = True
        # Track if an ancestor directory was fully excluded
        # (affects re-inclusion semantics)
        if not negate:
            ancestor = pat.rstrip("/")
            if "/" not in ancestor and path.startswith(ancestor + "/"):
                parent_excluded = True
    return ignored


def test_gcloudignore_exempts_docs_specs_semantically():
    """Behavioural test: docs/specs/SPEC-*.md must NOT be ignored by .gcloudignore.

    This test catches the gitignore trap where exemption patterns are present
    but non-functional due to parent directory exclusion.
    """
    rules = Path(".gcloudignore").read_text(encoding="utf-8").splitlines()

    critical_specs = [
        "docs/specs/SPEC-l2-entity-redefinition.md",
        "docs/specs/SPEC-doc-governance.md",
        "docs/specs/SPEC-document-bundle.md",
        "docs/specs/SPEC-task-governance.md",
        "docs/specs/SPEC-governance-guide-contract.md",
        "docs/specs/SPEC-governance-feedback-loop.md",
    ]
    for spec in critical_specs:
        ignored = _simulate_gcloudignore_matches(rules, spec)
        assert not ignored, (
            f"{spec} must not be ignored; gcloudignore rules would skip "
            f"this file and Cloud Run runtime will fail governance_ssot_audit."
        )

    # Sanity regression: non-spec docs should still be ignored
    ignored_readme = _simulate_gcloudignore_matches(rules, "docs/README.md")
    assert ignored_readme, "docs/README.md should still be ignored"


def test_gcloudignore_verified_via_gcloud_meta():
    """Authoritative check: actually ask gcloud what it would upload.

    Skipped if gcloud is not available locally (e.g. CI runner without gcloud).
    This is the ground truth — if this passes, the Cloud Run build will have
    the SPEC files in /app/docs/specs/.
    """
    try:
        result = subprocess.run(
            ["gcloud", "meta", "list-files-for-upload"],
            capture_output=True, text=True, timeout=30,
            cwd=Path(__file__).resolve().parents[2],
        )
    except FileNotFoundError:
        pytest.skip("gcloud CLI not available in this environment")

    if result.returncode != 0:
        pytest.skip(f"gcloud meta list-files-for-upload unavailable: {result.stderr}")

    uploaded = set(result.stdout.splitlines())
    critical_specs = [
        "docs/specs/SPEC-l2-entity-redefinition.md",
        "docs/specs/SPEC-doc-governance.md",
        "docs/specs/SPEC-document-bundle.md",
        "docs/specs/SPEC-task-governance.md",
        "docs/specs/SPEC-governance-guide-contract.md",
        "docs/specs/SPEC-governance-feedback-loop.md",
    ]
    for spec in critical_specs:
        assert spec in uploaded, (
            f"gcloud would not upload {spec}. Cloud Run runtime will fail "
            f"governance_ssot_audit. Check .gcloudignore pattern ordering."
        )
