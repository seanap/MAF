from pathlib import Path

import pytest

from app.rss import FeedStore, extract_torrent_id, normalize_rss_items, redact_url, validate_mam_feed_url


def test_feed_url_redaction_and_validation():
    url = "https://www.myanonamouse.net/rss.php?uid=1&passkey=secret&token=abc"
    assert validate_mam_feed_url(url) == url
    cdn_url = "https://02e0d.mrd.ninja/rss/1634bd1a"
    assert validate_mam_feed_url(cdn_url) == cdn_url
    redacted = redact_url(url)
    assert "secret" not in redacted
    assert "abc" not in redacted
    assert "[REDACTED]" in redacted
    cdn_redacted = redact_url("https://02e0d.mrd.ninja/rss/1634bd1a?x=1&passkey=secret")
    assert "1634bd1a" not in cdn_redacted
    assert "secret" not in cdn_redacted
    assert "/rss/[REDACTED]" in cdn_redacted


@pytest.mark.parametrize("url", ["http://127.0.0.1/feed", "file:///etc/passwd", "https://evil.example/rss"])
def test_rejects_non_mam_urls(url):
    with pytest.raises(ValueError):
        validate_mam_feed_url(url)


def test_extract_torrent_id_from_mam_links():
    assert extract_torrent_id("https://www.myanonamouse.net/t/123") == "123"
    assert extract_torrent_id("https://www.myanonamouse.net/tor/download.php?tid=456") == "456"


def test_normalize_rss_items_strips_private_urls():
    xml = """<?xml version="1.0"?><rss><channel><item><title><![CDATA[Book <script>bad</script>]]></title><link>https://www.myanonamouse.net/t/123?secret=abc&amp;passkey=secret</link><guid>https://www.myanonamouse.net/tor/download.php?tid=123&amp;passkey=secret</guid></item></channel></rss>"""
    items = normalize_rss_items(xml, feed_id=1)

    assert items[0]["torrent_id"] == "123"
    assert items[0]["canonical_key"] == "mam:torrent:123"
    assert "passkey" not in repr(items[0])
    assert "secret" not in repr(items[0])


def test_feed_store_create_redacts_url(tmp_path: Path):
    store = FeedStore(tmp_path / "feeds.sqlite3")
    feed = store.create_feed("Author", "author", "https://www.myanonamouse.net/rss.php?passkey=secret")

    assert feed["id"] == 1
    assert "secret" not in feed["url_redacted"]
    assert "url_secret" not in feed



def test_feed_store_qol_fields_and_combined_visibility(tmp_path: Path):
    store = FeedStore(tmp_path / "feeds.sqlite3")
    one = store.create_feed("One", "series", "https://www.myanonamouse.net/rss.php?passkey=one", color="#fff7e6", display_limit=1)
    two = store.create_feed("Two", "author", "https://www.myanonamouse.net/rss.php?passkey=two", show_in_combined=False)

    assert one["color"] == "#fff7e6"
    assert one["display_limit"] == 1
    assert two["show_in_combined"] is False
    assert "url_secret" not in repr(one)

    store.upsert_items(one["id"], [
        {"canonical_key": "mam:torrent:1", "torrent_id": "1", "title": "A", "details_url": "https://www.myanonamouse.net/t/1"},
        {"canonical_key": "mam:torrent:2", "torrent_id": "2", "title": "B", "details_url": "https://www.myanonamouse.net/t/2"},
    ])
    store.upsert_items(two["id"], [{"canonical_key": "mam:torrent:3", "torrent_id": "3", "title": "C", "details_url": "https://www.myanonamouse.net/t/3"}])

    combined = store.list_items(combined=True)
    assert len(combined) == 1
    assert combined[0]["feed_name"] == "One"
    assert combined[0]["feed_color"] == "#fff7e6"
    assert store.list_items(feed_id=two["id"])[0]["title"] == "C"


def test_feed_store_patch_validates_color_and_clamps_limit(tmp_path: Path):
    store = FeedStore(tmp_path / "feeds.sqlite3")
    feed = store.create_feed("One", "series", "https://www.myanonamouse.net/rss.php?passkey=one")

    updated = store.update_feed(feed["id"], color="#ABCDEF", display_limit=9999, collapsed=True, show_in_combined=False)

    assert updated["color"] == "#abcdef"
    assert updated["display_limit"] == 500
    assert updated["collapsed"] is True
    assert updated["show_in_combined"] is False
    with pytest.raises(ValueError):
        store.update_feed(feed["id"], color="red")
