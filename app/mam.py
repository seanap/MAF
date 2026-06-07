from __future__ import annotations

import re
import json
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from .models import canonical_key

MAX_TORRENT_BYTES = 2 * 1024 * 1024


class MamError(RuntimeError):
    pass


class InvalidTorrentId(ValueError):
    pass


def validate_torrent_content(content: bytes, content_type: str = "") -> bytes:
    if not content:
        raise MamError("MAM returned an empty torrent")
    if len(content) > MAX_TORRENT_BYTES:
        raise MamError("MAM torrent response exceeded size limit")
    prefix = content[:128].lstrip().lower()
    ctype = (content_type or "").lower()
    if prefix.startswith(b"<html") or "text/html" in ctype:
        raise MamError("MAM returned HTML instead of a torrent")
    return content


def validate_torrent_id(value: str | int | None) -> str:
    tid = str(value or "").strip()
    if not re.fullmatch(r"\d+", tid):
        raise InvalidTorrentId("Invalid MAM torrent id")
    return tid


def build_mam_cookie(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "mam_id=" in raw or "mam_session=" in raw:
        return raw
    if "=" not in raw and ";" not in raw:
        return f"mam_id={raw}"
    return raw


class MamClient:
    def __init__(self, base_url: str, cookie: str, *, timeout: float = 30.0, client: httpx.AsyncClient | None = None) -> None:
        parsed = urlparse((base_url or "https://www.myanonamouse.net").rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise MamError("Invalid MAM base URL")
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.host = parsed.netloc
        self.cookie = build_mam_cookie(cookie)
        self.timeout = timeout
        self.client = client

    def build_download_url(self, torrent_id: str | int, *, use_wedge: bool = False) -> str:
        tid = validate_torrent_id(torrent_id)
        query = {"tid": tid}
        if use_wedge:
            query["fl"] = "1"
        return f"{self.base_url}/tor/download.php?{urlencode(query)}"

    def headers(self) -> dict[str, str]:
        return {
            "Cookie": self.cookie,
            "User-Agent": "MAF/0.1",
            "Accept": "application/x-bittorrent, */*",
            "Referer": f"{self.base_url}/",
        }

    async def fetch_torrent_bytes(self, torrent_id: str | int, *, use_wedge: bool = False) -> bytes:
        if not self.cookie:
            raise MamError("MAM cookie is not configured")
        url = self.build_download_url(torrent_id, use_wedge=use_wedge)
        try:
            if self.client is not None:
                response = await self.client.get(url, headers=self.headers(), follow_redirects=False)
            else:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                    response = await client.get(url, headers=self.headers())
        except httpx.HTTPError as exc:
            raise MamError("MAM torrent fetch failed") from exc
        if response.is_redirect:
            loc = response.headers.get("location", "")
            if urlparse(loc).netloc and urlparse(loc).netloc != self.host:
                raise MamError("MAM redirected to an unexpected host")
            raise MamError("MAM returned a redirect instead of a torrent")
        if response.status_code != 200:
            raise MamError(f"MAM returned HTTP {response.status_code}")
        return validate_torrent_content(response.content or b"", response.headers.get("content-type", ""))

    async def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.cookie:
            raise MamError("MAM cookie is not configured")
        headers = {
            "Cookie": self.cookie,
            "Content-Type": "application/json",
            "Accept": "application/json, */*",
            "User-Agent": "MAF/0.1",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        }
        try:
            if self.client is not None:
                response = await self.client.post(f"{self.base_url}/tor/js/loadSearchJSONbasic.php", headers=headers, params={"dlLink": "1"}, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(f"{self.base_url}/tor/js/loadSearchJSONbasic.php", headers=headers, params={"dlLink": "1"}, json=payload)
        except httpx.HTTPError as exc:
            raise MamError("MAM search failed") from exc
        if response.status_code != 200:
            raise MamError(f"MAM search returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise MamError("MAM search returned invalid JSON") from exc


def _flatten(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return _flatten(json.loads(stripped))
            except ValueError:
                pass
        return value
    if isinstance(value, dict):
        names = []
        for x in value.values():
            if isinstance(x, (list, tuple)) and x:
                names.append(str(x[0]))
            else:
                names.append(str(x))
        return ", ".join(names)
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if value is None:
        return ""
    return str(value)


def description_preview(value: Any, *, limit: int = 360) -> str:
    text = re.sub(r"<[^>]+>", " ", _flatten(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,;:-") + "…"


def normalize_mam_result(item: dict[str, Any]) -> dict[str, Any]:
    tid = validate_torrent_id(item.get("id") or item.get("tid"))
    title = item.get("title") or item.get("name") or ""
    title_l = str(title).lower()
    fmt = item.get("format") or item.get("filetype") or ("M4B" if "m4b" in title_l else "")
    free = item.get("isFree", item.get("is_freeleech", item.get("freeleech")))
    is_freeleech = None if free is None else str(free).strip().lower() in {"1", "true", "yes", "free"}
    return {
        "canonical_key": canonical_key(tid),
        "source": "search",
        "torrent_id": tid,
        "title": title,
        "author": _flatten(item.get("author_info") or item.get("author")),
        "narrator": _flatten(item.get("narrator_info") or item.get("narrator")),
        "series": _flatten(item.get("series_info") or item.get("series")),
        "format": fmt,
        "format_confident": bool(str(fmt).lower() == "m4b" or "m4b" in title_l),
        "size": item.get("size"),
        "seeders": item.get("seeders"),
        "leechers": item.get("leechers"),
        "uploaded_at": item.get("added"),
        "description_preview": description_preview(item.get("description") or item.get("descr") or item.get("synopsis") or ""),
        "cover_url": f"/api/mam/cover/{tid}",
        "details_url": f"https://www.myanonamouse.net/t/{tid}",
        "is_freeleech": is_freeleech,
    }
