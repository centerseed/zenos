"""Document type aliases, canonical mapping, and source helpers (ADR-022).

Pure data module — no IO, no external dependencies.
Used by search handlers for transparent expansion,
read handlers for canonical_type computation,
and write handlers for source_id generation.
"""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------
# 11 universal document categories
# ---------------------------------------------------------------
VALID_DOC_TYPES: frozenset[str] = frozenset({
    "SPEC",
    "DECISION",
    "DESIGN",
    "PLAN",
    "REPORT",
    "CONTRACT",
    "GUIDE",
    "MEETING",
    "REFERENCE",
    "TEST",
    "OTHER",
})

# ---------------------------------------------------------------
# Legacy → canonical mapping (used for search expansion)
# ---------------------------------------------------------------
DOC_TYPE_ALIASES: dict[str, str] = {
    "ADR": "DECISION",
    "TD": "DESIGN",
    "TC": "TEST",
    "PB": "GUIDE",
    "REF": "REFERENCE",
}

# Reverse mapping: canonical → list of legacy aliases
_REVERSE_ALIASES: dict[str, list[str]] = {}
for _legacy, _canonical in DOC_TYPE_ALIASES.items():
    _REVERSE_ALIASES.setdefault(_canonical, []).append(_legacy)


def canonical_type(doc_type: str) -> str:
    """Return the canonical document type for a given type string.

    - Legacy types (ADR, TD, etc.) map to their canonical form.
    - New types and unmapped types return as-is.
    - SC has no fixed mapping, returns as-is.
    """
    return DOC_TYPE_ALIASES.get(doc_type, doc_type)


def expand_for_search(doc_type: str) -> list[str]:
    """Expand a doc_type query to include both legacy and canonical forms.

    Examples:
        expand_for_search("ADR")       -> ["ADR", "DECISION"]
        expand_for_search("DECISION")  -> ["DECISION", "ADR"]
        expand_for_search("PLAN")      -> ["PLAN"]
        expand_for_search("SC")        -> ["SC"]  (no fixed mapping)
    """
    upper = doc_type.upper()
    result = [upper]

    # If it's a legacy alias, add its canonical form
    if upper in DOC_TYPE_ALIASES:
        result.append(DOC_TYPE_ALIASES[upper])

    # If it's a canonical type, add all legacy aliases
    if upper in _REVERSE_ALIASES:
        for alias in _REVERSE_ALIASES[upper]:
            if alias not in result:
                result.append(alias)

    return result


def is_known_doc_type(doc_type: str) -> bool:
    """Check if a doc_type is a known valid type (new or legacy)."""
    upper = doc_type.upper()
    return upper in VALID_DOC_TYPES or upper in DOC_TYPE_ALIASES or upper == "SC"


def generate_source_id() -> str:
    """Generate a new UUID v4 source_id for a document source (ADR-022 D4)."""
    return str(uuid.uuid4())


def ensure_source_ids(sources: list[dict]) -> list[dict]:
    """Ensure every source in the list has a source_id.

    Existing source_ids are preserved. Missing ones are generated.
    This is used during write operations to backfill source_ids
    for legacy sources that predate ADR-022.
    """
    for src in sources:
        if not src.get("source_id"):
            src["source_id"] = generate_source_id()
    return sources
