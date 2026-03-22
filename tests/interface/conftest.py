"""Ensure GITHUB_TOKEN is set before tools.py is imported.

tools.py initializes GitHubAdapter at module level, which requires GITHUB_TOKEN.
In test environment we set a dummy value so the module can load.
"""

import os

os.environ.setdefault("GITHUB_TOKEN", "test-dummy-token")
