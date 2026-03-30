"""Tests for scripts/provision_customer.py.

Coverage
--------
- build_admin_partner_doc: correct fields for admin (no sharedPartnerId)
- build_member_partner_doc: correct fields for member (sharedPartnerId = admin_id)
- _provision_member: validation of required flags (member-email, member-display-name, admin-id)
- main: --member mode routes to _provision_member, default routes to _provision_admin
- Dry-run output for both modes

All Firestore interactions are mocked — no real Firebase project required.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2] / "scripts"))

from provision_customer import (  # noqa: E402
    _provision_admin,
    _provision_member,
    build_admin_partner_doc,
    build_member_partner_doc,
)

ADMIN_ID = "admin-partner-001"
ADMIN_EMAIL = "admin@example.com"
MEMBER_EMAIL = "member@example.com"


# ---------------------------------------------------------------------------
# build_admin_partner_doc
# ---------------------------------------------------------------------------

class TestBuildAdminPartnerDoc:
    def test_admin_doc_has_correct_fields(self):
        doc = build_admin_partner_doc(ADMIN_EMAIL, "Admin User")
        assert doc["email"] == ADMIN_EMAIL
        assert doc["displayName"] == "Admin User"
        assert doc["isAdmin"] is True
        assert doc["status"] == "active"
        assert "apiKey" in doc
        assert "createdAt" in doc
        assert "updatedAt" in doc

    def test_admin_doc_has_no_shared_partner_id(self):
        """Admin partner doc must NOT set sharedPartnerId (null means self-is-admin)."""
        doc = build_admin_partner_doc(ADMIN_EMAIL, "Admin User")
        assert "sharedPartnerId" not in doc, (
            "Admin partner must not have sharedPartnerId — it IS the canonical partition key"
        )

    def test_admin_doc_strips_and_lowercases_email(self):
        doc = build_admin_partner_doc("  ADMIN@EXAMPLE.COM  ", "Admin")
        assert doc["email"] == ADMIN_EMAIL

    def test_admin_doc_strips_display_name(self):
        doc = build_admin_partner_doc(ADMIN_EMAIL, "  Admin User  ")
        assert doc["displayName"] == "Admin User"

    def test_admin_doc_generates_unique_api_keys(self):
        doc1 = build_admin_partner_doc(ADMIN_EMAIL, "Admin")
        doc2 = build_admin_partner_doc(ADMIN_EMAIL, "Admin")
        assert doc1["apiKey"] != doc2["apiKey"]


# ---------------------------------------------------------------------------
# build_member_partner_doc
# ---------------------------------------------------------------------------

class TestBuildMemberPartnerDoc:
    def test_member_doc_has_correct_fields(self):
        doc = build_member_partner_doc(MEMBER_EMAIL, "Member User", ADMIN_ID)
        assert doc["email"] == MEMBER_EMAIL
        assert doc["displayName"] == "Member User"
        assert doc["isAdmin"] is False
        assert doc["status"] == "active"
        assert "apiKey" in doc
        assert "createdAt" in doc

    def test_member_doc_has_shared_partner_id_set_to_admin_id(self):
        """Non-admin member must have sharedPartnerId = admin_id for partition routing."""
        doc = build_member_partner_doc(MEMBER_EMAIL, "Member User", ADMIN_ID)
        assert "sharedPartnerId" in doc, "Member must have sharedPartnerId field"
        assert doc["sharedPartnerId"] == ADMIN_ID, (
            f"sharedPartnerId should be {ADMIN_ID!r}, got {doc['sharedPartnerId']!r}"
        )

    def test_member_doc_strips_and_lowercases_email(self):
        doc = build_member_partner_doc("  MEMBER@EXAMPLE.COM  ", "Member", ADMIN_ID)
        assert doc["email"] == MEMBER_EMAIL

    def test_member_doc_is_not_admin(self):
        doc = build_member_partner_doc(MEMBER_EMAIL, "Member", ADMIN_ID)
        assert doc["isAdmin"] is False


# ---------------------------------------------------------------------------
# _provision_member — validation of required flags
# ---------------------------------------------------------------------------

class TestProvisionMemberValidation:
    def _make_args(self, **kwargs) -> SimpleNamespace:
        defaults = {
            "project": "test-project",
            "admin_email": ADMIN_EMAIL,
            "display_name": "Admin",
            "dry_run": True,
            "member": True,
            "member_email": MEMBER_EMAIL,
            "member_display_name": "Member User",
            "admin_id": ADMIN_ID,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_missing_member_email_returns_error_code(self):
        args = self._make_args(member_email=None)
        result = _provision_member(args)
        assert result == 2

    def test_missing_member_display_name_returns_error_code(self):
        args = self._make_args(member_display_name=None)
        result = _provision_member(args)
        assert result == 2

    def test_missing_admin_id_returns_error_code(self):
        args = self._make_args(admin_id=None)
        result = _provision_member(args)
        assert result == 2

    def test_dry_run_prints_shared_partner_id(self, capsys):
        args = self._make_args(dry_run=True)
        result = _provision_member(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "sharedPartnerId" in captured.out
        assert ADMIN_ID in captured.out

    def test_dry_run_does_not_call_firestore(self):
        args = self._make_args(dry_run=True)
        with patch("provision_customer.firestore") as mock_firestore:
            _provision_member(args)
            mock_firestore.Client.assert_not_called()


# ---------------------------------------------------------------------------
# _provision_admin — dry-run path
# ---------------------------------------------------------------------------

class TestProvisionAdminDryRun:
    def _make_args(self, **kwargs) -> SimpleNamespace:
        defaults = {
            "project": "test-project",
            "admin_email": ADMIN_EMAIL,
            "display_name": "Admin User",
            "dry_run": True,
            "member": False,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_dry_run_returns_zero(self):
        args = self._make_args()
        result = _provision_admin(args)
        assert result == 0

    def test_dry_run_does_not_call_firestore(self):
        args = self._make_args()
        with patch("provision_customer.firestore") as mock_firestore:
            _provision_admin(args)
            mock_firestore.Client.assert_not_called()
