# MAF — MAM Audiobook Finder

MAF is a small self-hosted web frontend for a MAM-only audiobook request workflow.
It searches MyAnonamouse, monitors configured MAM RSS feeds, applies a smart Freeleech Wedge policy, and sends server-fetched `.torrent` bytes to qBittorrent.

The intended production flow is deliberately boring:

```text
MAF → fetch torrent from MAM server-side → qBittorrent → Audiobookshelf scan/match
```

qBittorrent downloads to its own configured default folder. Audiobookshelf scans that same folder and handles matching/metadata. MAF does **not** need to mount, move, rename, hardlink, transcode, or organize your audiobook files.

<img width="3497" height="1999" alt="Screenshot 2026-06-07 102233(1)" src="https://github.com/user-attachments/assets/cf701285-f317-4b47-a9fd-f0e6553b0f5e" />
<img width="3493" height="1701" alt="Screenshot 2026-06-07 102343" src="https://github.com/user-attachments/assets/42a98a85-b809-4855-a83e-339251b2ba2b" />

## Features

- MAM catalog search focused on audiobook/M4B results.
- Remote request UI designed for LAN/Tailscale use.
- MAM RSS watch dashboard for authors, series, narrators, or custom MAM feeds.
- Server-side torrent fetch and qBittorrent Web API upload.
- Local grabbed/hidden history to suppress already-requested items.
- Smart Freeleech Wedge decision policy.
- Cover thumbnails with enlarged hover/click preview.
- Docker/Dockge-friendly deployment: one `/data` volume plus environment variables.

## Non-goals

- No Calibre integration.
- No Audiobookshelf importing or metadata management.
- No file moving/copying/hardlinking/renaming/transcoding in the default workflow.
- Not safe to expose directly to the public Internet.

## Quick start with Docker Compose / Dockge

Create a stack directory containing `docker-compose.yml` and `.env`.

### `docker-compose.yml`

```yaml
services:
  mam-audiofinder:
    image: seanap/maf:latest
    container_name: mam-audiofinder
    ports:
      - "8008:8080"
    env_file:
      - .env
    volumes:
      - ./data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s
```

### `.env`

```env
TZ=America/New_York
DATA_DIR=/data
DISABLE_SETUP=1
LIBRARY_MODE=qbit_abs_shared
ENABLE_IMPORT=0

# Paste your MAM cookie value. Do not commit this file.
MAM_COOKIE=replace_me

# qBittorrent Web UI URL reachable from the MAF container.
QB_URL=http://qbittorrent:8080
QB_USER=replace_me
QB_PASS=replace_me

# Leave blank to let qBittorrent use its configured default save path.
QB_SAVEPATH=
QB_CATEGORY=maf
QB_TAGS=MAM,audiobook,maf

WEDGE_MODE=smart
WEDGE_UNKNOWN_FALLBACK=true

# Optional. Only needed for the history "Resolve ABS" helper.
ABS_URL=
ABS_TOKEN=
ABS_LIBRARY_ID=
```

Then deploy:

```bash
docker compose up -d
docker compose logs -f mam-audiofinder
```

Open `http://<docker-host>:8008/` from your trusted LAN or Tailscale network.

## Configuration notes

- `/data/config.json`, if created by the setup UI, overrides matching environment variables.
- `DISABLE_SETUP=1` hides and disables the setup UI after configuration.
- Leave `QB_SAVEPATH` empty for the recommended qBit+Audiobookshelf shared-folder workflow.
- MAM RSS feed URLs are stored server-side in `/data/history.db`; browser/API responses return redacted feed URLs.
- The app fetches private `.torrent` bytes server-side. Private MAM download URLs are not sent to the browser or qBittorrent.

## Security notes

MAF stores private MAM cookies/RSS URLs and can add torrents to qBittorrent. Treat it as a control-plane service.

- Run only on trusted LAN/Tailscale, or put a real authenticated reverse proxy in front of it.
- Never commit `.env`, `/data`, SQLite DBs, logs containing cookies, or generated config files.
- Rotate your MAM cookie if it was ever committed or pasted into public logs.
- Do not expose raw MAF directly to the public Internet.

## Local development

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest -q
python3 -m py_compile app/main.py app/mam.py app/qbit.py app/history_store.py app/wedge.py app/presets.py app/rss.py app/models.py
node --check app/static/app.js
docker compose config >/tmp/maf-compose-config.txt
```

## Project documentation

- [Deployment notes](docs/DEPLOYMENT.md)
- [Development guide](docs/DEVELOPMENT.md)
