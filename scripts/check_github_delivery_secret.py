#!/usr/bin/env python3
"""Validate the GitHub delivery secret used by Cloud Run MCP deployments.

This script never prints the token value. It only reports whether the secret
can authenticate against GitHub's `/user` endpoint.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import httpx


def _read_secret(project_id: str, secret_name: str, version: str) -> str:
    result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            version,
            f"--secret={secret_name}",
            f"--project={project_id}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _probe_github(token: str) -> tuple[int, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.get("https://api.github.com/user", headers=headers)
    message = ""
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        message = str(payload.get("login") or payload.get("message") or "")
    return response.status_code, message


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--secret-name", default="github-token")
    parser.add_argument("--version", default="latest")
    args = parser.parse_args()

    try:
        token = _read_secret(args.project_id, args.secret_name, args.version)
    except subprocess.CalledProcessError as exc:
        print(json.dumps({
            "status": "error",
            "error": "SECRET_READ_FAILED",
            "message": exc.stderr.strip() or "failed to read secret",
        }, ensure_ascii=False))
        return 2

    if not token:
        print(json.dumps({
            "status": "error",
            "error": "EMPTY_SECRET",
            "message": "secret value is empty",
        }, ensure_ascii=False))
        return 2

    try:
        status_code, message = _probe_github(token)
    except Exception as exc:  # pragma: no cover - network specific
        print(json.dumps({
            "status": "error",
            "error": "GITHUB_UNREACHABLE",
            "message": str(exc),
        }, ensure_ascii=False))
        return 3

    if status_code == 200:
        print(json.dumps({
            "status": "ok",
            "http_status": status_code,
            "login": message,
        }, ensure_ascii=False))
        return 0

    print(json.dumps({
        "status": "rejected",
        "error": "INVALID_GITHUB_TOKEN",
        "http_status": status_code,
        "message": message or "GitHub authentication failed",
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
