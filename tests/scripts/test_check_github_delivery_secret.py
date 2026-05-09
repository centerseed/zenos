from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_github_delivery_secret import main


def test_main_returns_ok_when_github_accepts_token(monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="secret-token\n", stderr=""),
    )

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"login": "centerseed"}

    with patch("scripts.check_github_delivery_secret.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = None
        client.get.return_value = response
        client_cls.return_value = client

        monkeypatch.setattr(
            "sys.argv",
            ["check_github_delivery_secret.py", "--project-id", "zenos-naruvia"],
        )
        rc = main()

    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "ok"
    assert captured["login"] == "centerseed"


def test_main_returns_rejected_when_github_rejects_token(monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="secret-token\n", stderr=""),
    )

    response = MagicMock()
    response.status_code = 401
    response.json.return_value = {"message": "Bad credentials"}

    with patch("scripts.check_github_delivery_secret.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = None
        client.get.return_value = response
        client_cls.return_value = client

        monkeypatch.setattr(
            "sys.argv",
            ["check_github_delivery_secret.py", "--project-id", "zenos-naruvia"],
        )
        rc = main()

    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["status"] == "rejected"
    assert captured["error"] == "INVALID_GITHUB_TOKEN"
    assert captured["http_status"] == 401


def test_main_returns_error_when_secret_read_fails(monkeypatch, capsys):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="permission denied")

    monkeypatch.setattr(subprocess, "run", _raise)
    monkeypatch.setattr(
        "sys.argv",
        ["check_github_delivery_secret.py", "--project-id", "zenos-naruvia"],
    )

    rc = main()

    captured = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert captured["status"] == "error"
    assert captured["error"] == "SECRET_READ_FAILED"
