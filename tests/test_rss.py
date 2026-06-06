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
