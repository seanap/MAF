import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def load_app(tmp_path: Path):
    for key in ["DATA_DIR", "DB_PATH", "APP_CONFIG_PATH", "MAM_COOKIE", "QB_URL", "QB_SAVEPATH", "WEDGE_MODE", "WEDGE_UNKNOWN_FALLBACK"]:
        os.environ.pop(key, None)
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["DB_PATH"] = str(tmp_path / "data" / "maf.sqlite3")
    os.environ["APP_CONFIG_PATH"] = str(tmp_path / "data" / "config.json")
    os.environ["MAM_COOKIE"] = "mam_id=fake"
    os.environ["QB_URL"] = "http://192.168.1.125:8080"
    sys.modules.pop("app.main", None)
    return importlib.import_module("app.main")


def test_api_add_fetches_torrent_bytes_and_marks_history(monkeypatch, tmp_path):
    mod = load_app(tmp_path)
    calls = []

    class FakeMam:
        def __init__(self, base, cookie):
            assert cookie == "mam_id=fake"
        async def fetch_torrent_bytes(self, tid, use_wedge=False):
            calls.append(("mam", tid, use_wedge))
            return b"d4:infodee"

    class FakeQbit:
        def __init__(self, url, user, password):
            assert url == "http://192.168.1.125:8080"
        async def add_torrent_bytes(self, **kwargs):
            calls.append(("qbit", kwargs))
            assert kwargs["savepath"] == ""
            assert kwargs["torrent_bytes"] == b"d4:infodee"
            return "grabbed"

    monkeypatch.setattr(mod, "MamClient", FakeMam)
    monkeypatch.setattr(mod, "QbitClient", FakeQbit)
    client = TestClient(mod.app)

    response = client.post("/api/torrents/add", json={"torrent_id": "123", "title": "Book", "is_freeleech": False})

    assert response.status_code == 200
    assert response.json()["state"] == "grabbed"
    assert response.json()["wedge_used"] is True
    assert calls[0] == ("mam", "123", True)
    assert calls[1][0] == "qbit"
    assert mod.history_store.is_grabbed("mam:torrent:123") is True


def test_api_add_rejects_invalid_id_before_network(monkeypatch, tmp_path):
    mod = load_app(tmp_path)
    monkeypatch.setattr(mod, "MamClient", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call MAM")))
    client = TestClient(mod.app)

    response = client.post("/api/torrents/add", json={"torrent_id": "https://evil/1"})

    assert response.status_code == 422


def test_api_search_uses_preset_and_annotates_history(monkeypatch, tmp_path):
    mod = load_app(tmp_path)
    mod.history_store.mark_grabbed("mam:torrent:123", torrent_id="123")

    class FakeMam:
        def __init__(self, base, cookie):
            pass
        async def search(self, payload):
            assert payload["tor"]["text"] == "dune"
            assert payload["tor"]["sortType"] == "dateDesc"
            assert payload["perpage"] == 100
            return {"total": 2, "data": [
                {"id": "123", "title": "Dune M4B", "format": "M4B", "isFree": "1"},
                {"id": "456", "title": "Dune MP3", "format": "MP3", "isFree": "1"},
            ]}

    monkeypatch.setattr(mod, "MamClient", FakeMam)
    client = TestClient(mod.app)

    response = client.get("/api/search?q=dune&window=all&sort=dateDesc&perpage=25")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    item = response.json()["items"][0]
    assert item["canonical_key"] == "mam:torrent:123"
    assert item["grabbed"] is True
    assert "dl" not in item


def test_api_search_respects_requested_perpage_after_m4b_filter(monkeypatch, tmp_path):
    mod = load_app(tmp_path)

    class FakeMam:
        def __init__(self, base, cookie):
            pass
        async def search(self, payload):
            assert payload["perpage"] == 100  # fetch wide for server-side M4B filtering
            return {"total": 40, "data": [
                {"id": str(i), "title": f"Book {i} M4B", "format": "M4B", "isFree": "1"}
                for i in range(40)
            ]}

    monkeypatch.setattr(mod, "MamClient", FakeMam)
    client = TestClient(mod.app)

    response = client.get("/api/search?q=&window=past_3_months&sort=snatchedDesc&perpage=25")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 25
    assert data["shown"] == 25
    assert data["total"] == 40
    assert data["perpage"] == 25


def test_feed_api_exposes_local_urls_and_lists_items(tmp_path):
    mod = load_app(tmp_path)
    client = TestClient(mod.app)

    created = client.post("/api/feeds", json={"name": "Series", "kind": "series", "url": "https://www.myanonamouse.net/rss.php?passkey=secret"})

    assert created.status_code == 200
    assert created.json()["url"] == "https://www.myanonamouse.net/rss.php?passkey=secret"
    assert "url_secret" not in created.json()
    listed = client.get("/api/feeds")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["url"].endswith("passkey=secret")


def test_feed_api_patch_and_delete(tmp_path):
    mod = load_app(tmp_path)
    client = TestClient(mod.app)
    created = client.post("/api/feeds", json={"name": "Series", "kind": "series", "url": "https://www.myanonamouse.net/rss.php?passkey=secret"})
    assert created.status_code == 200

    patched = client.patch(f"/api/feeds/{created.json()['id']}", json={"name": "Updated", "enabled": False})
    assert patched.status_code == 200
    assert patched.json()["name"] == "Updated"
    assert patched.json()["url"].endswith("passkey=secret")
    deleted = client.delete(f"/api/feeds/{created.json()['id']}")
    assert deleted.status_code == 200


def test_legacy_add_delegates_to_safe_numeric_add(monkeypatch, tmp_path):
    mod = load_app(tmp_path)

    class FakeMam:
        def __init__(self, base, cookie): pass
        async def fetch_torrent_bytes(self, tid, use_wedge=False): return b"d4:infodee"

    class FakeQbit:
        def __init__(self, url, user, password): pass
        async def add_torrent_bytes(self, **kwargs): return "grabbed"

    monkeypatch.setattr(mod, "MamClient", FakeMam)
    monkeypatch.setattr(mod, "QbitClient", FakeQbit)
    client = TestClient(mod.app)

    assert client.post("/add", json={"id": "123", "title": "Book"}).status_code == 200
    assert client.post("/add", json={"dl": "private-token"}).status_code == 422


def test_frontend_uses_new_api_contracts():
    app_js = Path("app/static/app.js").read_text()

    assert "it.torrent_id || it.id" in app_js
    assert "fetch('/api/history')" in app_js
    assert "fetch('/api/torrents/add'" in app_js
    assert "coverCell" in app_js
    assert "No rows match the active filters" in app_js


def test_root_page_renders_review_ui(tmp_path):
    mod = load_app(tmp_path)
    client = TestClient(mod.app)

    resp = client.get('/')
    assert resp.status_code == 200
    assert 'Audiobook Finder' in resp.text
    assert 'MAM RSS Watch Dashboard' in resp.text
