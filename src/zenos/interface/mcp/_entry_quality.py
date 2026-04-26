"""Quality checks for durable ontology entries."""

from __future__ import annotations

import re

VALID_ENTRY_TYPES = {"decision", "insight", "limitation", "change", "context"}

_DURABLE_MARKERS = (
    "because",
    "why",
    "tradeoff",
    "decision",
    "limitation",
    "constraint",
    "invariant",
    "原因",
    "因為",
    "決策",
    "取捨",
    "限制",
    "約束",
    "不變",
    "必須",
    "不得",
    "風險",
    "後續",
)

_COMPLETION_MARKERS = (
    "qa pass",
    "pass",
    "passed",
    "done",
    "completed",
    "實作完成",
    "交付",
    "完成：",
    "已完成",
    "通過",
    "驗證指令",
    "pytest",
    "xcodebuild",
    "build succeeded",
    "deployed",
    "部署",
)


def entry_quality_issue(content: str, entry_type: str | None = None) -> str | None:
    """Return a rejection/skip reason when entry content is not durable knowledge."""
    text = (content or "").strip()
    if not text:
        return "entry_content_empty"
    if len(text) < 12:
        return "entry_content_too_thin"

    lower = text.lower()
    has_durable_marker = any(marker in lower or marker in text for marker in _DURABLE_MARKERS)
    has_completion_marker = any(marker in lower or marker in text for marker in _COMPLETION_MARKERS)

    if re.search(r"\bAC-[A-Z0-9_-]+", text) and has_completion_marker and not has_durable_marker:
        return "entry_is_acceptance_report"
    if has_completion_marker and not has_durable_marker:
        return "entry_is_completion_report"
    if re.search(r"\b[\w/.-]+\.(py|ts|tsx|swift|sql|md):\d+\b", text) and not has_durable_marker:
        return "entry_is_code_trace"
    if (entry_type or "").strip() == "change" and not has_durable_marker and has_completion_marker:
        return "change_entry_needs_durable_why_or_boundary"
    return None

