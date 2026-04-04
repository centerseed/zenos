"""Tests for domain/validation.py — pure function validation utilities."""

from __future__ import annotations

import pytest

from zenos.domain.validation import (
    find_similar_items,
    validate_task_confirm,
    validate_task_linked_entities,
    validate_task_title,
)


# ──────────────────────────────────────────────
# find_similar_items
# ──────────────────────────────────────────────

def test_find_similar_items_exact_match():
    items = [{"id": "1", "name": "hello world"}]
    results = find_similar_items("hello world", items)
    assert len(results) == 1
    assert results[0]["similarity_score"] == 1.0


def test_find_similar_items_partial_match():
    items = [{"id": "1", "name": "hello world"}, {"id": "2", "name": "foo bar"}]
    results = find_similar_items("hello there", items, threshold=0.1)
    ids = [r["id"] for r in results]
    assert "1" in ids
    assert "2" not in ids


def test_find_similar_items_below_threshold_filtered():
    items = [{"id": "1", "name": "completely different text"}]
    results = find_similar_items("hello world", items, threshold=0.9)
    assert results == []


def test_find_similar_items_empty_name():
    items = [{"id": "1", "name": "hello"}]
    assert find_similar_items("", items) == []


def test_find_similar_items_empty_list():
    assert find_similar_items("hello", []) == []


def test_find_similar_items_limit_respected():
    items = [{"id": str(i), "name": f"hello world item{i}"} for i in range(10)]
    results = find_similar_items("hello world", items, threshold=0.1, limit=3)
    assert len(results) <= 3


def test_find_similar_items_sorted_by_score_desc():
    items = [
        {"id": "1", "name": "alpha beta gamma"},
        {"id": "2", "name": "alpha beta"},
        {"id": "3", "name": "alpha"},
    ]
    results = find_similar_items("alpha beta gamma delta", items, threshold=0.0)
    scores = [r["similarity_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


# ──────────────────────────────────────────────
# validate_task_title
# ──────────────────────────────────────────────

def test_validate_task_title_valid():
    errors, warnings = validate_task_title("Implement OAuth login flow")
    assert errors == []
    assert warnings == []


def test_validate_task_title_too_short_error():
    errors, warnings = validate_task_title("Fix")
    assert any("過短" in e for e in errors)


def test_validate_task_title_starts_with_english_stopword():
    errors, warnings = validate_task_title("Task to fix the login bug")
    assert any("停用詞" in e for e in errors)


def test_validate_task_title_starts_with_chinese_stopword():
    errors, warnings = validate_task_title("任務修復登入問題")
    assert any("停用詞" in e for e in errors)


def test_validate_task_title_warning_for_short_but_valid():
    errors, warnings = validate_task_title("Fix bug")
    assert errors == []
    assert any("偏短" in w for w in warnings)


def test_validate_task_title_exactly_4_chars_no_error():
    errors, warnings = validate_task_title("done")
    assert not any("過短" in e for e in errors)


# ──────────────────────────────────────────────
# validate_task_linked_entities
# ──────────────────────────────────────────────

def test_validate_task_linked_entities_all_valid():
    errors, warnings = validate_task_linked_entities(["e1", "e2"], {"e1", "e2", "e3"})
    assert errors == []
    assert warnings == []


def test_validate_task_linked_entities_some_invalid():
    errors, warnings = validate_task_linked_entities(["e1", "e99"], {"e1"})
    assert any("e99" in e for e in errors)


def test_validate_task_linked_entities_empty_list_warning():
    errors, warnings = validate_task_linked_entities([], {"e1"})
    assert errors == []
    assert warnings != []


# ──────────────────────────────────────────────
# validate_task_confirm
# ──────────────────────────────────────────────

def test_validate_task_confirm_review_without_result_error():
    errors, warnings = validate_task_confirm("review", False)
    assert any("result" in e for e in errors)


def test_validate_task_confirm_review_with_result_ok():
    errors, warnings = validate_task_confirm("review", True)
    assert errors == []


def test_validate_task_confirm_non_review_status_ok():
    errors, warnings = validate_task_confirm("in_progress", False)
    assert errors == []
