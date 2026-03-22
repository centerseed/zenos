"""Setup for interface tests.

tools.py initializes repos at module level, which call get_db() → firestore.AsyncClient.
In CI there are no GCP credentials, so we must mock get_db() before tools.py is imported.
Also sets GITHUB_TOKEN for GitHubAdapter.
"""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("GITHUB_TOKEN", "test-dummy-token")

# Mock get_db before any firestore_repo class is instantiated
_mock_db = MagicMock()
patch("zenos.infrastructure.firestore_repo.get_db", return_value=_mock_db).start()
