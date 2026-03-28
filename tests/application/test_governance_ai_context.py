from __future__ import annotations

from zenos.application.governance_ai import (
    ConsolidationMergeGroup,
    ConsolidationProposal,
    GovernanceAI,
    GovernanceInference,
)


class _FakeLLM:
    def __init__(self, result):
        self._result = result
        self.last_messages = None

    def chat_structured(self, **kwargs):
        self.last_messages = kwargs.get("messages")
        return self._result


class _FailingLLM:
    """Fake LLM that always raises an exception."""

    def chat_structured(self, **kwargs):
        raise RuntimeError("LLM service unavailable")


def test_infer_all_uses_richer_context_in_prompt():
    llm = _FakeLLM(GovernanceInference(rels=[]))
    ai = GovernanceAI(llm)

    result = ai.infer_all(
        entity_data={
            "name": "計費模型",
            "summary": "定義方案與升降級規則",
            "tags": {"what": ["pricing"], "why": "revenue", "how": "rules", "who": ["pm"]},
            "_global_context": {
                "entity_counts": {"product": 1, "module": 2},
                "document_count": 3,
                "recurring_terms": ["pricing", "checkout", "subscription"],
                "active_products": ["p1|ZenOS|AI context layer"],
                "active_modules": ["m1|支付流程|處理金流扣款與重試"],
                "impact_target_hints": ["m1|支付流程|處理金流扣款與重試"],
            },
        },
        existing_entities=[
            {
                "id": "m1",
                "name": "支付流程",
                "type": "module",
                "summary": "處理金流扣款與重試",
                "tags": {"what": ["payment"], "who": ["engineer"]},
                "doc_hints": ["checkout.md: 描述扣款流程"],
                "impacts_to": ["支付流程 -> 對帳: 扣款失敗率變更→對帳告警門檻要調整"],
                "impacted_by": [],
            }
        ],
        unlinked_docs=[
            {
                "id": "doc-1",
                "title": "pricing-rules.md",
                "summary": "方案切換與升降級條件",
                "source_uri": "docs/pricing-rules.md",
            }
        ],
    )
    assert result is not None
    user_prompt = llm.last_messages[1]["content"]
    assert "新實體 tags" in user_prompt
    assert "全局統合 context" in user_prompt
    assert "recurring_terms" in user_prompt
    assert "doc_hints" in user_prompt
    assert "impacts_to" in user_prompt
    assert "pricing-rules.md" in user_prompt
    assert "方案切換與升降級條件" in user_prompt


def test_infer_all_includes_insufficient_context_contract():
    llm = _FakeLLM(GovernanceInference(rels=[]))
    ai = GovernanceAI(llm)
    ai.infer_all(
        entity_data={"name": "A", "summary": "B"},
        existing_entities=[{"id": "x", "name": "X", "type": "module", "summary": "S", "tags": {}}],
        unlinked_docs=[],
    )
    system_prompt = llm.last_messages[0]["content"]
    assert "impacts_context_status" in system_prompt
    assert "impacts_context_gaps" in system_prompt
    assert "Step 1 建立全景理解" in system_prompt
    assert "三問篩選閘" in system_prompt


# ===================================================================
# GovernanceAI.consolidate_entries tests (T3)
# ===================================================================

def _make_entries(count: int) -> list[dict]:
    return [
        {"id": f"entry-{i}", "type": "insight", "content": f"Insight number {i}"}
        for i in range(count)
    ]


def test_consolidate_entries_returns_proposal_on_success():
    """consolidate_entries returns ConsolidationProposal when LLM succeeds."""
    proposal = ConsolidationProposal(
        entity_id="ent-1",
        entity_name="ZenOS",
        merge_groups=[
            ConsolidationMergeGroup(
                source_entry_ids=["entry-0", "entry-1"],
                merged_content="Merged insight",
            )
        ],
        keep_as_is=[f"entry-{i}" for i in range(2, 20)],
        estimated_after_count=19,
    )
    llm = _FakeLLM(proposal)
    ai = GovernanceAI(llm)

    result = ai.consolidate_entries(
        entity_id="ent-1",
        entity_name="ZenOS",
        entries=_make_entries(20),
    )

    assert result is not None
    assert result.entity_id == "ent-1"
    assert result.entity_name == "ZenOS"
    assert len(result.merge_groups) == 1
    assert result.estimated_after_count == 19


def test_consolidate_entries_overrides_entity_fields():
    """consolidate_entries overrides entity_id/entity_name from LLM output."""
    proposal = ConsolidationProposal(
        entity_id="wrong-id",
        entity_name="Wrong Name",
        merge_groups=[],
        keep_as_is=[f"entry-{i}" for i in range(20)],
        estimated_after_count=20,
    )
    llm = _FakeLLM(proposal)
    ai = GovernanceAI(llm)

    result = ai.consolidate_entries(
        entity_id="correct-id",
        entity_name="Correct Name",
        entries=_make_entries(20),
    )

    assert result is not None
    assert result.entity_id == "correct-id"
    assert result.entity_name == "Correct Name"


def test_consolidate_entries_returns_none_on_llm_failure():
    """consolidate_entries returns None (not crashes) when LLM fails."""
    ai = GovernanceAI(_FailingLLM())

    result = ai.consolidate_entries(
        entity_id="ent-1",
        entity_name="ZenOS",
        entries=_make_entries(20),
    )

    assert result is None


def test_consolidate_entries_returns_none_for_empty_entries():
    """consolidate_entries returns None immediately when entries list is empty."""
    llm = _FakeLLM(None)
    ai = GovernanceAI(llm)

    result = ai.consolidate_entries(
        entity_id="ent-1",
        entity_name="ZenOS",
        entries=[],
    )

    assert result is None
