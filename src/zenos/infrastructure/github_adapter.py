"""GitHub API implementation of the SourceAdapter protocol."""

from __future__ import annotations

import base64
import os
import re
from urllib.parse import unquote

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_API_BASE = "https://api.github.com"

_URL_PATTERN = re.compile(
    r"https?://github\.com/"
    r"(?P<owner>[^/]+)/"
    r"(?P<repo>[^/]+)/"
    r"(?:blob|tree|raw)/"
    r"(?P<ref>[^/]+)/"
    r"(?P<path>.+)"
)

_SHORT_PATTERN = re.compile(
    r"^(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<path>.+)$"
)


def _get_token() -> str:
    return os.environ.get("GITHUB_TOKEN", "")


def _get_default_owner() -> str:
    return os.environ.get("GITHUB_DEFAULT_OWNER", "havital")


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def parse_github_url(uri: str) -> tuple[str, str, str, str]:
    """Parse a GitHub URL into (owner, repo, path, ref).

    Supported formats:
    - ``https://github.com/owner/repo/blob/ref/path/to/file``
    - ``https://github.com/owner/repo/tree/ref/path/to/dir``
    - ``https://github.com/owner/repo/raw/ref/path/to/file``
    - ``owner/repo/path/to/file`` (short form, ref defaults to ``main``)

    Raises ``ValueError`` if the URI cannot be parsed.
    """
    uri = uri.strip()

    # Full GitHub URL
    m = _URL_PATTERN.match(uri)
    if m:
        return (
            unquote(m.group("owner")),
            unquote(m.group("repo")),
            unquote(m.group("path")),
            unquote(m.group("ref")),
        )

    # Short form: owner/repo/path (assumes ref=main)
    m = _SHORT_PATTERN.match(uri)
    if m:
        return (
            m.group("owner"),
            m.group("repo"),
            m.group("path"),
            "main",
        )

    raise ValueError(f"Cannot parse GitHub URI: {uri}")


# ---------------------------------------------------------------------------
# GitHubAdapter
# ---------------------------------------------------------------------------


class GitHubAdapter:
    """Reads file content from GitHub via the Contents API.

    Implements the ``SourceAdapter`` protocol defined in ``domain/repositories.py``.
    """

    def __init__(self, token: str | None = None) -> None:
        self._token = token or _get_token()
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    async def read_content(self, uri: str) -> str:
        """Fetch the text content of a file from GitHub.

        Parameters
        ----------
        uri:
            A GitHub URL (blob/tree/raw format) or short ``owner/repo/path`` form.

        Returns
        -------
        str
            The decoded text content of the file.

        Raises
        ------
        FileNotFoundError
            If the file or repo does not exist (HTTP 404).
        PermissionError
            If access is denied (HTTP 403, non-rate-limit).
        RuntimeError
            If rate-limited (HTTP 429) or secondary rate limit (403 with
            ``rate limit`` in message).
        ValueError
            If the URI cannot be parsed or the file is too large (>100 MB).
        """
        owner, repo, path, ref = parse_github_url(uri)
        content = await self._fetch_contents(owner, repo, path, ref)
        return content

    async def _fetch_contents(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        """Use the Contents API; fall back to Blob API for large files."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers, params=params)

            if resp.status_code == 429:
                raise RuntimeError(f"GitHub API rate limited while fetching {path}")

            if resp.status_code == 403:
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                message = body.get("message", "")
                # Secondary rate limit
                if "rate limit" in message.lower():
                    raise RuntimeError(f"GitHub API rate limited while fetching {path}")
                # File too large -> try blob API
                if "too large" in message.lower() or resp.headers.get("content-length", "0") == "0":
                    return await self._fetch_via_blob(client, owner, repo, path, ref)
                raise PermissionError(
                    f"Permission denied for {owner}/{repo}/{path}: {message}"
                )

            if resp.status_code == 404:
                raise FileNotFoundError(
                    f"GitHub 404: path='{path}' not found in repo='{owner}/{repo}' (ref={ref})"
                )

            resp.raise_for_status()
            data = resp.json()

            # Directory listing (type == list)
            if isinstance(data, list):
                raise ValueError(
                    f"URI points to a directory, not a file: {owner}/{repo}/{path}"
                )

            encoding = data.get("encoding", "")
            if encoding == "base64":
                raw = base64.b64decode(data["content"])
                return raw.decode("utf-8")

            # If the file is > 1 MB, the Contents API returns only metadata
            # with a ``git_url`` pointing to the blob.
            if data.get("size", 0) > 1_000_000 or encoding == "none":
                return await self._fetch_via_blob(client, owner, repo, path, ref)

            # Fallback: content might be returned inline without encoding
            if "content" in data:
                return data["content"]

            raise ValueError(
                f"Unexpected response format for {owner}/{repo}/{path}"
            )

    async def _fetch_via_blob(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> str:
        """Fetch file content via the Git Blob API for files > 1 MB.

        Flow:
        1. Get the tree SHA for the ref.
        2. Walk the tree to find the blob SHA for the path.
        3. Fetch the blob content.
        """
        # Step 1: Get commit -> tree SHA
        commit_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{ref}"
        resp = await client.get(commit_url, headers=self._headers)
        self._check_response(resp, f"{owner}/{repo} ref={ref}")
        tree_sha = resp.json()["commit"]["tree"]["sha"]

        # Step 2: Resolve path segments through nested trees
        parts = path.strip("/").split("/")
        current_sha = tree_sha

        for i, part in enumerate(parts):
            tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{current_sha}"
            resp = await client.get(tree_url, headers=self._headers)
            self._check_response(resp, f"tree {current_sha}")
            tree_data = resp.json()

            found = False
            for item in tree_data.get("tree", []):
                if item["path"] == part:
                    current_sha = item["sha"]
                    found = True
                    break

            if not found:
                raise FileNotFoundError(
                    f"GitHub 404: path segment '{part}' not found in repo='{owner}/{repo}', traversed='{'/'.join(parts[:i])}'"
                )

        # Step 3: Fetch the blob
        blob_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/blobs/{current_sha}"
        resp = await client.get(blob_url, headers=self._headers)
        self._check_response(resp, f"blob {current_sha}")
        blob = resp.json()

        size = blob.get("size", 0)
        if size > 100_000_000:  # 100 MB
            raise ValueError(
                f"File too large ({size} bytes): {owner}/{repo}/{path}"
            )

        raw = base64.b64decode(blob["content"])
        return raw.decode("utf-8")

    def _check_response(self, resp: httpx.Response, context: str) -> None:
        """Raise appropriate errors for non-2xx responses."""
        if resp.status_code == 429:
            raise RuntimeError(f"GitHub API rate limited ({context})")
        if resp.status_code == 403:
            body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            msg = body.get("message", "")
            if "rate limit" in msg.lower():
                raise RuntimeError(f"GitHub API rate limited ({context})")
            raise PermissionError(f"Permission denied ({context}): {msg}")
        if resp.status_code == 404:
            raise FileNotFoundError(f"Not found: {context}")
        resp.raise_for_status()
