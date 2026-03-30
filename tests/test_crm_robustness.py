import unittest
from datetime import datetime, timezone
from zenos.infrastructure.crm_sql_repo import _row_to_deal
from zenos.domain.crm_models import FunnelStage

class MockRecord(dict):
    def __getitem__(self, key):
        return super().get(key)

class TestCrmRobustness(unittest.TestCase):
    def test_row_to_deal_with_invalid_enum(self):
        # Simulate a record with a funnel_stage that is NOT in the Enum
        bad_row = MockRecord({
            "id": "1",
            "partner_id": "p1",
            "title": "Bad Deal",
            "company_id": "c1",
            "owner_partner_id": "u1",
            "funnel_stage": "INVALID_STAGE_STRING", # This would normally crash
            "amount_twd": 1000,
            "deal_type": "INVALID_TYPE",
            "source_type": "INVALID_SOURCE",
            "referrer": None,
            "expected_close_date": None,
            "signed_date": None,
            "scope_description": None,
            "deliverables": [],
            "notes": None,
            "is_closed_lost": False,
            "is_on_hold": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        
        # This should NOT raise ValueError
        deal = _row_to_deal(bad_row)
        
        # Verify it fell back to default
        self.assertEqual(deal.funnel_stage, FunnelStage.PROSPECT)
        self.assertIsNone(deal.deal_type)
        self.assertIsNone(deal.source_type)
        self.assertEqual(deal.title, "Bad Deal")

if __name__ == "__main__":
    unittest.main()
