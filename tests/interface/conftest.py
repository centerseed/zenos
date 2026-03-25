"""Setup for interface tests.

Interface tests should mock Firestore DB creation, but the patch must stay scoped
to interface tests only; otherwise integration tests will receive MagicMock
instead of a real AsyncClient.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("GITHUB_TOKEN", "test-dummy-token")


@pytest.fixture(autouse=True)
def _mock_firestore_get_db():
    """Patch get_db() only while interface tests are running."""
    mock_db = MagicMock()
    with patch("zenos.infrastructure.firestore_repo.get_db", return_value=mock_db):
        yield
