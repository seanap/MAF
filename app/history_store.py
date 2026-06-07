from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoryStore:
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
                CREATE TABLE IF NOT EXISTS item_state (
                  id INTEGER PRIMARY KEY,
                  canonical_key TEXT NOT NULL UNIQUE,
                  torrent_id TEXT,
                  title TEXT,
                  author TEXT,
                  narrator TEXT,
                  grabbed INTEGER NOT NULL DEFAULT 0,
                  hidden INTEGER NOT NULL DEFAULT 0,
                  qbit_hash TEXT,
                  wedge_used INTEGER,
                  wedge_reason TEXT,
                  error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            cols = {row["name"] for row in cx.execute("PRAGMA table_info(item_state)")}
            for column, ddl in {
                "abs_item_id": "TEXT NOT NULL DEFAULT ''",
                "abs_item_url": "TEXT NOT NULL DEFAULT ''",
                "abs_resolved_at": "TEXT NOT NULL DEFAULT ''",
                "abs_match_status": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if column not in cols:
                    cx.execute(f"ALTER TABLE item_state ADD COLUMN {column} {ddl}")
            cx.execute("CREATE INDEX IF NOT EXISTS idx_item_state_updated ON item_state(updated_at DESC)")

    def _row(self, key: str) -> dict[str, Any] | None:
        with self.connect() as cx:
            row = cx.execute("SELECT * FROM item_state WHERE canonical_key=?", (key,)).fetchone()
        return dict(row) if row else None

    def mark_grabbed(self, canonical_key: str, *, torrent_id: str = "", title: str = "", author: str = "", narrator: str = "", qbit_hash: str | None = None, wedge_used: bool | None = None, wedge_reason: str | None = None) -> dict[str, Any]:
        ts = now_iso()
        with self.connect() as cx:
            cx.execute(
                """
                INSERT INTO item_state (canonical_key, torrent_id, title, author, narrator, grabbed, hidden, qbit_hash, wedge_used, wedge_reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET
                  grabbed=1,
                  torrent_id=COALESCE(NULLIF(excluded.torrent_id,''), item_state.torrent_id),
                  title=COALESCE(NULLIF(excluded.title,''), item_state.title),
                  author=COALESCE(NULLIF(excluded.author,''), item_state.author),
                  narrator=COALESCE(NULLIF(excluded.narrator,''), item_state.narrator),
                  qbit_hash=COALESCE(excluded.qbit_hash, item_state.qbit_hash),
                  wedge_used=COALESCE(excluded.wedge_used, item_state.wedge_used),
                  wedge_reason=COALESCE(excluded.wedge_reason, item_state.wedge_reason),
                  updated_at=excluded.updated_at
                """,
                (canonical_key, torrent_id, title, author, narrator, qbit_hash, None if wedge_used is None else int(wedge_used), wedge_reason, ts, ts),
            )
        return self._row(canonical_key) or {}

    def mark_failed(self, canonical_key: str, *, torrent_id: str = "", title: str = "", error: str = "") -> dict[str, Any]:
        ts = now_iso()
        with self.connect() as cx:
            cx.execute(
                """
                INSERT INTO item_state (canonical_key, torrent_id, title, grabbed, hidden, error, created_at, updated_at)
                VALUES (?, ?, ?, 0, 0, ?, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET error=excluded.error, updated_at=excluded.updated_at
                """,
                (canonical_key, torrent_id, title, error[:300], ts, ts),
            )
        return self._row(canonical_key) or {}

    def hide(self, canonical_key: str) -> dict[str, Any]:
        ts = now_iso()
        with self.connect() as cx:
            cx.execute(
                """
                INSERT INTO item_state (canonical_key, hidden, grabbed, created_at, updated_at)
                VALUES (?, 1, 0, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET hidden=1, updated_at=excluded.updated_at
                """,
                (canonical_key, ts, ts),
            )
        return self._row(canonical_key) or {}

    def unhide(self, canonical_key: str) -> dict[str, Any]:
        ts = now_iso()
        with self.connect() as cx:
            cx.execute("UPDATE item_state SET hidden=0, updated_at=? WHERE canonical_key=?", (ts, canonical_key))
        return self._row(canonical_key) or {"canonical_key": canonical_key, "hidden": 0}

    def is_grabbed(self, canonical_key: str) -> bool:
        row = self._row(canonical_key)
        return bool(row and row.get("grabbed"))

    def is_hidden(self, canonical_key: str) -> bool:
        row = self._row(canonical_key)
        return bool(row and row.get("hidden"))

    def annotate_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keys = [item.get("canonical_key") for item in items if item.get("canonical_key")]
        states: dict[str, dict[str, Any]] = {}
        if keys:
            placeholders = ",".join("?" for _ in keys)
            with self.connect() as cx:
                for row in cx.execute(f"SELECT canonical_key, grabbed, hidden FROM item_state WHERE canonical_key IN ({placeholders})", keys):
                    states[row["canonical_key"]] = dict(row)
        out = []
        for item in items:
            state = states.get(item.get("canonical_key"), {})
            copy = dict(item)
            copy["grabbed"] = bool(state.get("grabbed", False))
            copy["hidden"] = bool(state.get("hidden", False))
            out.append(copy)
        return out

    def list_history(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as cx:
            rows = cx.execute("SELECT * FROM item_state ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_by_id(self, row_id: int) -> dict[str, Any] | None:
        with self.connect() as cx:
            row = cx.execute("SELECT * FROM item_state WHERE id=?", (row_id,)).fetchone()
        return dict(row) if row else None

    def update_abs(self, row_id: int, *, abs_item_id: str = "", abs_item_url: str = "", status: str = "") -> dict[str, Any] | None:
        ts = now_iso()
        with self.connect() as cx:
            cx.execute(
                "UPDATE item_state SET abs_item_id=?, abs_item_url=?, abs_match_status=?, abs_resolved_at=?, updated_at=? WHERE id=?",
                (abs_item_id or "", abs_item_url or "", status or "", ts, ts, row_id),
            )
        return self.get_by_id(row_id)

    def delete_id(self, row_id: int) -> None:
        with self.connect() as cx:
            cx.execute("DELETE FROM item_state WHERE id=?", (row_id,))
