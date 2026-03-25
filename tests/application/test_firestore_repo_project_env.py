from __future__ import annotations

import importlib


def test_get_db_uses_google_cloud_project_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "customer-a")

    mod = importlib.import_module("zenos.infrastructure.firestore_repo")
    mod = importlib.reload(mod)

    captured = {}

    class DummyClient:
        def __init__(self, project: str):
            captured["project"] = project

    monkeypatch.setattr(mod.firestore, "AsyncClient", DummyClient)
    mod._db = None
    _ = mod.get_db()

    assert captured["project"] == "customer-a"


def test_get_db_falls_back_to_default_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    mod = importlib.import_module("zenos.infrastructure.firestore_repo")
    mod = importlib.reload(mod)

    captured = {}

    class DummyClient:
        def __init__(self, project: str):
            captured["project"] = project

    monkeypatch.setattr(mod.firestore, "AsyncClient", DummyClient)
    mod._db = None
    _ = mod.get_db()

    assert captured["project"] == "zenos-naruvia"
