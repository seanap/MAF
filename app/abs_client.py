from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


class AbsError(Exception):
    pass


@dataclass
class AbsMatch:
    status: str
    item_id: str = ""
    item_url: str = ""


class AbsClient:
    def __init__(self, base_url: str, token: str = "", library_id: str = "") -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.library_id = library_id or ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def item_url(self, item_id: str) -> str:
        return f"{self.base_url}/item/{quote(str(item_id))}"

    def search_url(self, title: str) -> str:
        return f"{self.base_url}/search?query={quote(title or '')}"

    async def search_books(self, title: str) -> list[dict[str, Any]]:
        if not self.configured:
            raise AbsError("Audiobookshelf API is not configured")
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"q": title, "query": title, "limit": 10}
        endpoints = []
        if self.library_id:
            endpoints.append(f"/api/libraries/{quote(self.library_id)}/items")
        endpoints.append("/api/search")
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            last_error = None
            for endpoint in endpoints:
                try:
                    resp = await client.get(f"{self.base_url}{endpoint}", params=params)
                    if resp.status_code in (404, 405):
                        continue
                    if resp.status_code >= 400:
                        last_error = f"ABS HTTP {resp.status_code}"
                        continue
                    data = resp.json()
                    return self._extract_items(data)
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = str(exc)
            raise AbsError(last_error or "ABS search failed")

    def _extract_items(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if not isinstance(data, dict):
            return []
        for key in ("items", "book", "libraryItems", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        media = data.get("media")
        if isinstance(media, dict):
            return [data]
        return []


def _norm(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _field(item: dict[str, Any], *keys: str) -> str:
    cur: Any = item
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return ""
    if isinstance(cur, list):
        return ", ".join(str(x.get("name", x)) if isinstance(x, dict) else str(x) for x in cur)
    return "" if cur is None else str(cur)


def score_abs_candidate(item: dict[str, Any], *, title: str, author: str = "") -> int:
    wanted_title = _norm(title)
    wanted_author = _norm(author)
    cand_title = _norm(_field(item, "media", "metadata", "title") or _field(item, "title") or _field(item, "name"))
    cand_author = _norm(_field(item, "media", "metadata", "authorName") or _field(item, "media", "metadata", "authors") or _field(item, "author"))
    score = 0
    if wanted_title and cand_title:
        if wanted_title == cand_title:
            score += 90
        elif wanted_title in cand_title or cand_title in wanted_title:
            score += 60
    if wanted_author and cand_author:
        if wanted_author == cand_author:
            score += 30
        elif wanted_author in cand_author or cand_author in wanted_author:
            score += 15
    return score


def choose_abs_match(items: list[dict[str, Any]], *, title: str, author: str = "", base_url: str = "", direct_item_urls: bool = False) -> AbsMatch:
    scored = [(score_abs_candidate(item, title=title, author=author), item) for item in items]
    scored = [(score, item) for score, item in scored if score >= 60]
    if not scored:
        return AbsMatch(status="not_found")
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return AbsMatch(status="ambiguous")
    item = scored[0][1]
    item_id = str(item.get("id") or item.get("libraryItemId") or item.get("itemId") or "")
    if not item_id:
        return AbsMatch(status="ambiguous")
    item_url = ""
    if base_url:
        if direct_item_urls:
            item_url = f"{base_url.rstrip('/')}/item/{quote(item_id)}"
        else:
            item_url = f"{base_url.rstrip('/')}/search?query={quote(title or '')}"
    return AbsMatch(status="matched", item_id=item_id, item_url=item_url)
