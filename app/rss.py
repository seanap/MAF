from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .models import canonical_key

MAM_HOSTS = {"www.myanonamouse.net", "myanonamouse.net"}
MAM_RSS_HOST_SUFFIXES = (".mrd.ninja",)
SECRET_QUERY_KEYS = {"passkey", "token", "auth", "key", "uid", "secret"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_url(url: str) -> str:
    parsed = urlparse(url or "")
    query = parse_qs(parsed.query, keep_blank_values=True)
    safe = []
    for key, values in query.items():
        safe.append((key, "[REDACTED]" if key.lower() in SECRET_QUERY_KEYS else (values[0] if values else "")))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(safe), "")).replace("%5B", "[").replace("%5D", "]")


def validate_mam_feed_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    host_allowed = hostname in MAM_HOSTS or any(hostname.endswith(suffix) for suffix in MAM_RSS_HOST_SUFFIXES)
    if parsed.scheme != "https" or not host_allowed:
        raise ValueError("Only HTTPS MAM RSS URLs are allowed")
    if not parsed.path:
        raise ValueError("Feed URL path required")
    return url


def extract_torrent_id(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    qs = parse_qs(parsed.query)
    for key in ("tid", "id"):
        if key in qs and qs[key] and re.fullmatch(r"\d+", qs[key][0]):
            return qs[key][0]
    m = re.search(r"/t/(\d+)", parsed.path)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:tid|id)=(\d+)\b", value)
    return m.group(1) if m else None


def _text(elem: ET.Element, name: str) -> str:
    found = elem.find(name)
    return "" if found is None or found.text is None else found.text.strip()


def normalize_rss_items(xml_text: str, *, feed_id: int) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError("Malformed RSS/XML") from exc
    items = []
    for elem in root.findall(".//item"):
        title = _text(elem, "title")
        link = _text(elem, "link")
        guid = _text(elem, "guid")
        tid = extract_torrent_id(link) or extract_torrent_id(guid)
        if not tid:
            continue
        items.append({
            "feed_id": feed_id,
            "canonical_key": canonical_key(tid),
            "torrent_id": tid,
            "title": title,
            "details_url": f"https://www.myanonamouse.net/t/{tid}",
            "source": "rss",
            "format": "M4B" if "m4b" in title.lower() else "",
        })
    return items


class FeedStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self.connect() as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS feeds (
                  id INTEGER PRIMARY KEY,
                  name TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  url_secret TEXT NOT NULL,
                  url_redacted TEXT NOT NULL,
                  enabled INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS rss_items (
                  id INTEGER PRIMARY KEY,
                  feed_id INTEGER NOT NULL,
                  canonical_key TEXT NOT NULL,
                  torrent_id TEXT NOT NULL,
                  title TEXT,
                  details_url TEXT,
                  first_seen_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  UNIQUE(feed_id, canonical_key)
                )
                """
            )

    def _public_feed(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d.pop("url_secret", None)
        return d

    def create_feed(self, name: str, kind: str, url: str, enabled: bool = True) -> dict[str, Any]:
        kind = (kind or "custom").strip().lower()
        if kind not in {"author", "series", "narrator", "custom"}:
            raise ValueError("Invalid feed kind")
        name = " ".join((name or "").split())[:120]
        if not name:
            raise ValueError("Feed name required")
        url = validate_mam_feed_url(url)
        ts = now_iso()
        with self.connect() as cx:
            cur = cx.execute(
                "INSERT INTO feeds (name, kind, url_secret, url_redacted, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, kind, url, redact_url(url), int(enabled), ts, ts),
            )
            row = cx.execute("SELECT * FROM feeds WHERE id=?", (cur.lastrowid,)).fetchone()
        return self._public_feed(row)

    def list_feeds(self) -> list[dict[str, Any]]:
        with self.connect() as cx:
            rows = cx.execute("SELECT * FROM feeds ORDER BY id").fetchall()
        return [self._public_feed(row) for row in rows]

    def get_secret_url(self, feed_id: int) -> str | None:
        with self.connect() as cx:
            row = cx.execute("SELECT url_secret FROM feeds WHERE id=? AND enabled=1", (feed_id,)).fetchone()
        return row["url_secret"] if row else None

    def update_feed(self, feed_id: int, *, name: str | None = None, kind: str | None = None, url: str | None = None, enabled: bool | None = None) -> dict[str, Any] | None:
        current = None
        with self.connect() as cx:
            current = cx.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
        if not current:
            return None
        data = dict(current)
        if name is not None:
            data["name"] = " ".join(name.split())[:120]
        if kind is not None:
            kind = kind.strip().lower()
            if kind not in {"author", "series", "narrator", "custom"}:
                raise ValueError("Invalid feed kind")
            data["kind"] = kind
        if url is not None:
            url = validate_mam_feed_url(url)
            data["url_secret"] = url
            data["url_redacted"] = redact_url(url)
        if enabled is not None:
            data["enabled"] = int(enabled)
        data["updated_at"] = now_iso()
        with self.connect() as cx:
            cx.execute("UPDATE feeds SET name=?, kind=?, url_secret=?, url_redacted=?, enabled=?, updated_at=? WHERE id=?", (data["name"], data["kind"], data["url_secret"], data["url_redacted"], data["enabled"], data["updated_at"], feed_id))
            row = cx.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
        return self._public_feed(row)

    def delete_feed(self, feed_id: int) -> None:
        with self.connect() as cx:
            cx.execute("DELETE FROM feeds WHERE id=?", (feed_id,))

    def upsert_items(self, feed_id: int, items: list[dict[str, Any]]) -> dict[str, int]:
        ts = now_iso(); created = updated = 0
        with self.connect() as cx:
            for item in items:
                before = cx.execute("SELECT id FROM rss_items WHERE feed_id=? AND canonical_key=?", (feed_id, item["canonical_key"])).fetchone()
                cx.execute(
                    """
                    INSERT INTO rss_items (feed_id, canonical_key, torrent_id, title, details_url, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(feed_id, canonical_key) DO UPDATE SET title=excluded.title, details_url=excluded.details_url, last_seen_at=excluded.last_seen_at
                    """,
                    (feed_id, item["canonical_key"], item["torrent_id"], item.get("title"), item.get("details_url"), ts, ts),
                )
                if before: updated += 1
                else: created += 1
        return {"created_count": created, "updated_count": updated}

    def list_items(self, feed_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM rss_items" + (" WHERE feed_id=?" if feed_id else "") + " ORDER BY last_seen_at DESC"
        args = (feed_id,) if feed_id else ()
        with self.connect() as cx:
            rows = cx.execute(sql, args).fetchall()
        return [dict(row) for row in rows]
