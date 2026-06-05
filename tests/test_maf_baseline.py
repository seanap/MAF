import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def load_app(tmp_path: Path, **env):
    for key in [
        "DATA_DIR",
        "DB_PATH",
        "APP_CONFIG_PATH",
        "DISABLE_SETUP",
        "ENABLE_IMPORT",
        "LIBRARY_MODE",
        "MAM_COOKIE",
        "QB_URL",
    ]:
        os.environ.pop(key, None)
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["DB_PATH"] = str(tmp_path / "db" / "history.sqlite3")
    os.environ["APP_CONFIG_PATH"] = str(tmp_path / "config" / "config.json")
    os.environ.update({k: str(v) for k, v in env.items()})

    sys.modules.pop("app.main", None)
    return importlib.import_module("app.main")


def test_app_imports_without_existing_data_dir(tmp_path):
    missing_data_dir = tmp_path / "data"
    assert not missing_data_dir.exists()

    mod = load_app(tmp_path)

    assert not missing_data_dir.exists()
    assert (tmp_path / "db").exists()
    assert mod.DB_PATH == str(tmp_path / "db" / "history.sqlite3")


def test_health_endpoint_works_with_temp_db(tmp_path):
    mod = load_app(tmp_path)
    client = TestClient(mod.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_setup_disabled_blocks_setup_routes(tmp_path):
    mod = load_app(tmp_path, DISABLE_SETUP="1")
    client = TestClient(mod.app)

    assert client.get("/setup").status_code == 404
    assert client.post("/api/setup", json={}).status_code == 404


def test_import_workflow_disabled_by_default(tmp_path):
    mod = load_app(tmp_path)
    client = TestClient(mod.app)

    assert mod.settings.LIBRARY_MODE == "qbit_abs_shared"
    assert mod.settings.ENABLE_IMPORT is False
    assert client.get("/qb/torrents").status_code == 404
    response = client.post(
        "/import",
        json={"author": "A", "title": "T", "hash": "abc", "history_id": None},
    )
    assert response.status_code == 404


def test_import_workflow_requires_explicit_legacy_mode(tmp_path):
    mod = load_app(tmp_path, ENABLE_IMPORT="1", LIBRARY_MODE="legacy_import")

    assert mod.settings.ENABLE_IMPORT is True


def test_escape_helper_handles_cookie_forms(tmp_path):
    mod = load_app(tmp_path)

    assert mod.build_mam_cookie("") == ""
    assert mod.build_mam_cookie("abc123") == "mam_id=abc123"
    assert mod.build_mam_cookie("mam_id=abc123") == "mam_id=abc123"
