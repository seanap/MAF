from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .models import canonical_key

MAM_HOSTS = {"www.myanonamouse.net", "myanonamouse.net"}
MAM_RSS_HOST_SUFFIXES = (".mrd.ninja",)
SECRET_QUERY_KEYS = {"passkey", "token", "auth", "key", "uid", "secret"}
FEED_KINDS = {"author", "series", "narrator", "custom"}
DEFAULT_FEED_COLOR = "#eef6ff"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_url(url: str) -> str:
    parsed = urlparse(url or "")
    query = parse_qs(parsed.query, keep_blank_values=True)
    safe = []
    for key, values in query.items():
        safe.append((key, "[REDACTED]" if key.lower() in SECRET_QUERY_KEYS else (values[0] if values else "")))
    redacted = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(safe), ""))
    hostname = (parsed.hostname or "").lower()
    if any(hostname.endswith(s) for s in MAM_RSS_HOST_SUFFIXES) and parsed.path.startswith("/rss/"):
        redacted = urlunparse((parsed.scheme, parsed.netloc, "/rss/[REDACTED]", "", urlencode(safe), ""))
    return redacted.replace("%5B", "[").replace("%5D", "]")


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


def validate_color(color: str | None) -> str:
    color = (color or DEFAULT_FEED_COLOR).strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        raise ValueError("Feed color must be #RRGGBB")
    return color.lower()


def clamp_display_limit(value: int | str | None) -> int:
    try:
        n = int(value if value is not None else 15)
    except (TypeError, ValueError):
        n = 15
    return min(500, max(1, n))


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


def normalize_rss_datetime(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


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
        published_at = normalize_rss_datetime(_text(elem, "pubDate") or _text(elem, "dc:date") or _text(elem, "date"))
        description = _text(elem, "description")
        tid = extract_torrent_id(link) or extract_torrent_id(guid)
        if not tid:
            continue
        items.append({
            "feed_id": feed_id,
            "canonical_key": canonical_key(tid),
            "torrent_id": tid,
            "title": title,
            "details_url": f"https://www.myanonamouse.net/t/{tid}",
            "cover_url": f"/api/mam/cover/{tid}",
            "description": description,
            "site_added_at": published_at,
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

    def _ensure_column(self, cx: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column):
            raise ValueError("Unsafe SQLite identifier")
        cols = {row["name"] for row in cx.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            cx.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

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
                  cover_url TEXT,
                  description TEXT,
                  site_added_at TEXT,
                  rss_position INTEGER NOT NULL DEFAULT 0,
                  first_seen_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  UNIQUE(feed_id, canonical_key)
                )
                """
            )
            self._ensure_column(cx, "feeds", "color", f"TEXT NOT NULL DEFAULT '{DEFAULT_FEED_COLOR}'")
            self._ensure_column(cx, "feeds", "collapsed", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(cx, "feeds", "show_in_combined", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(cx, "feeds", "display_limit", "INTEGER NOT NULL DEFAULT 15")
            self._ensure_column(cx, "feeds", "last_refresh_status", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(cx, "feeds", "last_refresh_message", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(cx, "feeds", "last_refresh_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(cx, "rss_items", "cover_url", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(cx, "rss_items", "description", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(cx, "rss_items", "site_added_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(cx, "rss_items", "rss_position", "INTEGER NOT NULL DEFAULT 0")

    def _public_feed(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        # Local/private UI: expose the RSS URL for convenience. Keep url_redacted
        # as a compatibility alias for older frontend/tests.
        public_url = d.get("url_secret", d.get("url_redacted", ""))
        d["url"] = public_url
        d["url_redacted"] = public_url
        d.pop("url_secret", None)
        for key in ("enabled", "collapsed", "show_in_combined"):
            d[key] = bool(d.get(key))
        d["display_limit"] = clamp_display_limit(d.get("display_limit"))
        d["color"] = validate_color(d.get("color"))
        return d

    def create_feed(self, name: str, kind: str, url: str, enabled: bool = True, *, color: str | None = None, collapsed: bool = False, show_in_combined: bool = True, display_limit: int = 15) -> dict[str, Any]:
        kind = (kind or "custom").strip().lower()
        if kind not in FEED_KINDS:
            raise ValueError("Invalid feed kind")
        name = " ".join((name or "").split())[:120]
        if not name:
            raise ValueError("Feed name required")
        url = validate_mam_feed_url(url)
        color = validate_color(color)
        display_limit = clamp_display_limit(display_limit)
        ts = now_iso()
        with self.connect() as cx:
            cur = cx.execute(
                """
                INSERT INTO feeds (name, kind, url_secret, url_redacted, enabled, color, collapsed, show_in_combined, display_limit, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, kind, url, redact_url(url), int(enabled), color, int(collapsed), int(show_in_combined), display_limit, ts, ts),
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

    def update_feed(self, feed_id: int, *, name: str | None = None, kind: str | None = None, url: str | None = None, enabled: bool | None = None, color: str | None = None, collapsed: bool | None = None, show_in_combined: bool | None = None, display_limit: int | None = None, last_refresh_status: str | None = None, last_refresh_message: str | None = None, last_refresh_at: str | None = None) -> dict[str, Any] | None:
        with self.connect() as cx:
            current = cx.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
        if not current:
            return None
        data = dict(current)
        if name is not None:
            data["name"] = " ".join(name.split())[:120]
            if not data["name"]:
                raise ValueError("Feed name required")
        if kind is not None:
            kind = kind.strip().lower()
            if kind not in FEED_KINDS:
                raise ValueError("Invalid feed kind")
            data["kind"] = kind
        if url is not None and url.strip():
            url = validate_mam_feed_url(url)
            data["url_secret"] = url
            data["url_redacted"] = redact_url(url)
        if enabled is not None:
            data["enabled"] = int(enabled)
        if color is not None:
            data["color"] = validate_color(color)
        if collapsed is not None:
            data["collapsed"] = int(collapsed)
        if show_in_combined is not None:
            data["show_in_combined"] = int(show_in_combined)
        if display_limit is not None:
            data["display_limit"] = clamp_display_limit(display_limit)
        if last_refresh_status is not None:
            data["last_refresh_status"] = str(last_refresh_status)[:40]
        if last_refresh_message is not None:
            data["last_refresh_message"] = str(last_refresh_message)[:300]
        if last_refresh_at is not None:
            data["last_refresh_at"] = str(last_refresh_at)[:80]
        data["updated_at"] = now_iso()
        with self.connect() as cx:
            cx.execute(
                """
                UPDATE feeds SET name=?, kind=?, url_secret=?, url_redacted=?, enabled=?, color=?, collapsed=?, show_in_combined=?, display_limit=?, last_refresh_status=?, last_refresh_message=?, last_refresh_at=?, updated_at=? WHERE id=?
                """,
                (data["name"], data["kind"], data["url_secret"], data["url_redacted"], data["enabled"], data["color"], data["collapsed"], data["show_in_combined"], data["display_limit"], data["last_refresh_status"], data["last_refresh_message"], data["last_refresh_at"], data["updated_at"], feed_id),
            )
            row = cx.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
        return self._public_feed(row)

    def delete_feed(self, feed_id: int) -> None:
        with self.connect() as cx:
            cx.execute("DELETE FROM rss_items WHERE feed_id=?", (feed_id,))
            cx.execute("DELETE FROM feeds WHERE id=?", (feed_id,))

    def upsert_items(self, feed_id: int, items: list[dict[str, Any]]) -> dict[str, int]:
        ts = now_iso(); created = updated = 0
        with self.connect() as cx:
            for position, item in enumerate(items):
                before = cx.execute("SELECT id FROM rss_items WHERE feed_id=? AND canonical_key=?", (feed_id, item["canonical_key"])).fetchone()
                cx.execute(
                    """
                    INSERT INTO rss_items (feed_id, canonical_key, torrent_id, title, details_url, cover_url, description, site_added_at, rss_position, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(feed_id, canonical_key) DO UPDATE SET title=excluded.title, details_url=excluded.details_url, cover_url=excluded.cover_url, description=excluded.description, site_added_at=COALESCE(NULLIF(excluded.site_added_at, ''), rss_items.site_added_at), rss_position=excluded.rss_position, last_seen_at=excluded.last_seen_at
                    """,
                    (feed_id, item["canonical_key"], item["torrent_id"], item.get("title"), item.get("details_url"), item.get("cover_url") or f"/api/mam/cover/{item['torrent_id']}", item.get("description") or "", item.get("site_added_at") or "", position, ts, ts),
                )
                if before: updated += 1
                else: created += 1
        return {"created_count": created, "updated_count": updated}

    def list_items(self, feed_id: int | None = None, *, combined: bool = True, limit: int | None = None, apply_display_limit: bool = True) -> list[dict[str, Any]]:
        where = []
        args: list[Any] = []
        if feed_id:
            where.append("ri.feed_id=?")
            args.append(feed_id)
        elif combined:
            where.append("f.show_in_combined=1")
        sql = """
            SELECT ri.*, f.name AS feed_name, f.color AS feed_color, f.enabled AS feed_enabled,
                   f.show_in_combined AS feed_show_in_combined, f.display_limit AS feed_display_limit
            FROM rss_items ri
            JOIN feeds f ON f.id = ri.feed_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ri.feed_id, CASE WHEN ri.site_added_at IS NOT NULL AND ri.site_added_at != '' THEN 0 ELSE 1 END, ri.site_added_at DESC, ri.rss_position ASC, ri.id DESC"
        with self.connect() as cx:
            rows = [dict(row) for row in cx.execute(sql, args).fetchall()]
        grouped_counts: dict[int, int] = {}
        out = []
        for row in rows:
            fid = int(row["feed_id"])
            row["feed_enabled"] = bool(row.get("feed_enabled"))
            row["feed_show_in_combined"] = bool(row.get("feed_show_in_combined"))
            row["feed_color"] = validate_color(row.get("feed_color"))
            row_limit = clamp_display_limit(row.get("feed_display_limit")) if apply_display_limit and combined and not feed_id else 500
            grouped_counts[fid] = grouped_counts.get(fid, 0) + 1
            if grouped_counts[fid] > row_limit:
                continue
            out.append(row)
        out.sort(key=lambda r: (1 if (r.get("site_added_at") or "") else 0, r.get("site_added_at") or "", -int(r.get("rss_position") or 0)), reverse=True)
        if limit is not None:
            out = out[:clamp_display_limit(limit)]
        return out
