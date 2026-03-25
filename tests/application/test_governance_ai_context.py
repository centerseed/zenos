from __future__ import annotations

from zenos.application.governance_ai import GovernanceAI, GovernanceInference


class _FakeLLM:
    def __init__(self, result: GovernanceInference):
        self._result = result
        self.last_messages = None

    def chat_structured(self, **kwargs):
        self.last_messages = kwargs.get("messages")
        return self._result


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
