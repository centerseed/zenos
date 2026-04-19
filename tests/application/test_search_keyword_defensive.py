"""Regression: keyword_matches must tolerate malformed tag values.

DF-20260419-1 friction: search(collection='entities', query='test') raised
'list' object has no attribute 'lower' for some production data. Root cause
was legacy entities with nested list or non-string values in tags.what / who,
which bypass the str-assumed pool loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zenos.application.knowledge.search_service import keyword_matches


@dataclass
class _Tags:
    what: Any = None
    why: Any = None
    how: Any = None
    who: Any = None


@dataclass
class _Entity:
    name: str
    summary: str = ""
    tags: Any = None


def test_tolerates_nested_list_in_what():
    entity = _Entity(
        name="X",
        summary="",
        tags=_Tags(what=[["nested", "treasure"]], who=[]),
    )
    assert keyword_matches("treasure", entity) == 1


def test_tolerates_non_string_scalar_tags():
    entity = _Entity(
        name="X",
        summary="",
        tags=_Tags(what=[123, None, "gold"], why=None, how=[], who="solo-string"),
    )
    assert keyword_matches("gold", entity) == 1
    assert keyword_matches("solo", entity) == 1


def test_tolerates_none_tags():
    entity = _Entity(name="X", summary="body text", tags=None)
    assert keyword_matches("body", entity) == 1


def test_no_crash_on_all_malformed():
    entity = _Entity(
        name=None,  # should be handled by _push
        summary=None,
        tags=_Tags(what=[[[None]]], why=[], how=set(), who=None),
    )
    assert keyword_matches("nothing", entity) == 0
