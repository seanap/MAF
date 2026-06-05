# MAF Development Guide

MAF is Sean's private fork of `mam-audiofinder`, focused on one job: request MAM audiobooks remotely and send torrent bytes to local qBittorrent. qBit downloads to its configured default folder; Audiobookshelf scans that folder. MAF does not organize files.

## Architecture

- `app/main.py` — FastAPI app and API surface.
- `app/mam.py` — MAM-only search/download adapter.
- `app/qbit.py` — qBittorrent Web API adapter.
- `app/history_store.py` — grabbed/hidden state store.
- `app/wedge.py` — Freeleech Wedge policy.
- `app/presets.py` — advanced M4B search preset.
- `app/rss.py` — MAM RSS feed storage/parsing.
- `docs/specs/MAF_SPEC.md` — full product/environment specification.
- `docs/specs/NEXT_STEPS_DEVELOPMENT_SPECS.md` — implementation specs for current feature batch.
- `docs/specs/ADVERSARIAL_REVIEW_NEXT_STEPS.md` — adversarial review findings incorporated into implementation.

## Local test commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest -q
python3 -m py_compile app/main.py app/mam.py app/qbit.py app/history_store.py app/wedge.py app/presets.py app/rss.py app/models.py
node --check app/static/app.js
docker compose config >/tmp/maf-compose-config.txt
```

## Development rules

- Write tests first for behavior changes.
- Do not add Calibre behavior.
- Do not move/copy/hardlink/rename audiobook files.
- Do not send qBit private MAM URLs; fetch torrent bytes server-side and upload those bytes.
- Keep qBit save path blank unless deliberately overriding qBit defaults.
- Treat MAM cookies, qBit credentials, ABS tokens, and RSS URLs as secrets.
- Keep unit tests offline; fake MAM/qBit/ABS.

## Current API surface

- `GET /api/presets`
- `GET /api/status`
- `GET /api/search`
- `POST /api/torrents/add`
- `GET /api/history`
- `POST /api/history/hide`
- `POST /api/history/unhide`
- `POST /api/history/mark-grabbed`
- `GET /api/feeds`
- `POST /api/feeds`
- `POST /api/feeds/{feed_id}/refresh`
- `GET /api/rss/items`

Legacy routes remain for compatibility but new work should target `/api/*`.
