from __future__ import annotations

import re
from typing import Any

import httpx


class QbitError(RuntimeError):
    pass


def _tag_string(tags: str | list[str] | tuple[str, ...] | None) -> str:
    if tags is None:
        return ""
    if isinstance(tags, str):
        parts = tags.split(",")
    else:
        parts = list(tags)
    safe = []
    for tag in parts:
        t = str(tag).strip()
        if t:
            safe.append(t)
    return ",".join(safe)


def build_add_torrent_payload(*, torrent_bytes: bytes, filename: str, category: str = "", tags: str | list[str] | None = None, savepath: str = "") -> tuple[dict[str, str], dict[str, tuple[str, bytes, str]]]:
    filename = re.sub(r"[^A-Za-z0-9_.-]", "-", filename or "mam.torrent")[:128]
    data: dict[str, str] = {}
    if category:
        data["category"] = category
    tag_str = _tag_string(tags)
    if tag_str:
        data["tags"] = tag_str
    if savepath and savepath.strip():
        data["savepath"] = savepath.strip()
    files = {"torrents": (filename, torrent_bytes, "application/x-bittorrent")}
    return data, files


def validate_add_response(status_code: int, text: str) -> str:
    body = (text or "").strip()
    if status_code != 200:
        raise QbitError(f"qBit add returned HTTP {status_code}")
    lower = body.lower()
    if lower in {"ok", "ok."} or lower == "":
        return "grabbed"
    if "already" in lower or "duplicate" in lower or "exists" in lower:
        return "duplicate"
    raise QbitError("qBit add failed")


class QbitClient:
    def __init__(self, base_url: str, username: str = "", password: str = "", *, timeout: float = 30.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.username = username or ""
        self.password = password or ""
        self.timeout = timeout
        if not self.base_url:
            raise QbitError("qBit URL is not configured")

    async def login(self, client: httpx.AsyncClient) -> None:
        response = await client.post(f"{self.base_url}/api/v2/auth/login", data={"username": self.username, "password": self.password})
        text = response.text or ""
        if response.status_code == 200 and ("Ok" in text or text.strip() == ""):
            return
        raise QbitError("qBit login failed")

    async def status(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.login(client)
            version = await client.get(f"{self.base_url}/api/v2/app/version")
            api = await client.get(f"{self.base_url}/api/v2/app/webapiVersion")
            prefs = await client.get(f"{self.base_url}/api/v2/app/preferences")
        pref_json = {}
        try:
            pref_json = prefs.json()
        except Exception:
            pass
        return {
            "version": version.text.strip(),
            "webapi_version": api.text.strip(),
            "save_path": pref_json.get("save_path"),
            "bypass_local_auth": pref_json.get("bypass_local_auth"),
        }

    async def add_torrent_bytes(self, *, torrent_id: str, torrent_bytes: bytes, category: str = "", tags: str | list[str] | None = None, savepath: str = "") -> str:
        data, files = build_add_torrent_payload(
            torrent_bytes=torrent_bytes,
            filename=f"mam-{torrent_id}.torrent",
            category=category,
            tags=tags,
            savepath=savepath,
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.login(client)
            response = await client.post(f"{self.base_url}/api/v2/torrents/add", data=data, files=files)
        return validate_add_response(response.status_code, response.text)
