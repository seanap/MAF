from app.abs_client import choose_abs_match
from app.history_store import HistoryStore


def test_history_store_abs_fields_and_update(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    row = store.mark_grabbed("mam:torrent:123", torrent_id="123", title="Book", author="Author")

    assert row["abs_item_id"] == ""
    assert row["abs_match_status"] == ""

    updated = store.update_abs(row["id"], abs_item_id="li_123", abs_item_url="http://abs/item/li_123", status="matched")
    assert updated is not None

    assert updated["abs_item_id"] == "li_123"
    assert updated["abs_item_url"] == "http://abs/item/li_123"
    assert updated["abs_match_status"] == "matched"
    assert updated["abs_resolved_at"]


def test_choose_abs_match_exact_title_author():
    match = choose_abs_match([
        {"id": "bad", "media": {"metadata": {"title": "Other", "authorName": "Author"}}},
        {"id": "good", "media": {"metadata": {"title": "Book", "authorName": "Author"}}},
    ], title="Book", author="Author", base_url="http://abs")

    assert match.status == "matched"
    assert match.item_id == "good"
    assert match.item_url == "http://abs/search?query=Book"


def test_choose_abs_match_ambiguous_equal_scores():
    match = choose_abs_match([
        {"id": "one", "media": {"metadata": {"title": "Book", "authorName": "Author"}}},
        {"id": "two", "media": {"metadata": {"title": "Book", "authorName": "Author"}}},
    ], title="Book", author="Author", base_url="http://abs")

    assert match.status == "ambiguous"


def test_choose_abs_match_not_found():
    match = choose_abs_match([{"id": "bad", "media": {"metadata": {"title": "Other"}}}], title="Book", base_url="http://abs")

    assert match.status == "not_found"
