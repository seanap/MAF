# MAF Docker / Dockge Deployment

## Production shape

MAF should run as a small Docker service with only `/data` persisted. In the default workflow it does not need the Audiobookshelf library or qBittorrent download directory mounted because qBittorrent downloads to its configured default folder and Audiobookshelf scans that same folder.

Expose MAF only to a trusted LAN/Tailscale network unless you add authentication in front of it.

## Dockge compose

```yaml
services:
  mam-audiofinder:
    image: seanap/maf:latest
    container_name: mam-audiofinder
    restart: unless-stopped
    ports:
      - "8008:8080"
    env_file:
      - .env
    volumes:
      - ./data:/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s
```

## `.env`

```env
TZ=America/New_York
DATA_DIR=/data
DISABLE_SETUP=1
LIBRARY_MODE=qbit_abs_shared
ENABLE_IMPORT=0

MAM_COOKIE=replace_me

QB_URL=http://qbittorrent:8080
QB_USER=replace_me
QB_PASS=replace_me
QB_SAVEPATH=
QB_CATEGORY=maf
QB_TAGS=MAM,audiobook,maf

WEDGE_MODE=smart
WEDGE_UNKNOWN_FALLBACK=true

# Optional Audiobookshelf history resolver.
ABS_URL=
ABS_TOKEN=
ABS_LIBRARY_ID=
```

## Verification before production use

```bash
docker compose config
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:8008/health
```

Then open the UI from a trusted LAN/Tailscale client, add one known-safe MAM item, verify it appears in qBittorrent, and verify Audiobookshelf sees it after its scan.

## Security warning

MAF is a control-plane service. It stores a MAM cookie and private RSS URLs, and it can add torrents to qBittorrent.

- Do not commit `.env`, `/data`, SQLite DBs, or logs that may contain private values.
- Browser/API feed responses are redacted; `/data/history.db` still contains private RSS URLs by design.
- Do not publish the raw app to the public Internet.
