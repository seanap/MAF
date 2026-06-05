from pathlib import Path

from app.history_store import HistoryStore


def test_mark_grabbed_is_idempotent(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.sqlite3")

    first = store.mark_grabbed("mam:torrent:123", torrent_id="123", title="A")
    second = store.mark_grabbed("mam:torrent:123", torrent_id="123", title="A again")

    assert first["id"] == second["id"]
    assert store.is_grabbed("mam:torrent:123") is True
    assert len(store.list_history()) == 1


def test_hide_unhide_preserves_grabbed(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    key = "mam:torrent:123"
    store.mark_grabbed(key, torrent_id="123", title="A")
    store.hide(key)

    assert store.is_hidden(key) is True
    assert store.is_grabbed(key) is True

    store.unhide(key)
    assert store.is_hidden(key) is False
    assert store.is_grabbed(key) is True


def test_annotate_items_uses_canonical_key(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.mark_grabbed("mam:torrent:123", torrent_id="123", title="A")
    store.hide("mam:torrent:999")

    items = store.annotate_items([
        {"canonical_key": "mam:torrent:123", "title": "Different"},
        {"canonical_key": "mam:torrent:999", "title": "Hidden"},
    ])

    assert items[0]["grabbed"] is True
    assert items[0]["hidden"] is False
    assert items[1]["grabbed"] is False
    assert items[1]["hidden"] is True
