# MAF Docker and MAM Guide

## Dockge Deployment

MAF should run as a small Docker service with only `/data` persisted. In the default workflow it does not need the Audiobookshelf library or qBittorrent download directory mounted because qBittorrent downloads to its configured default folder and Audiobookshelf scans that same folder.

Expose MAF only to a trusted LAN/Tailscale network unless you add authentication in front of it.

### Dockge compose

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

### `.env`

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

### Verification before production use

```bash
docker compose config
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:8008/health
```

Then open the UI from a trusted LAN/Tailscale client, add one known-safe MAM item, verify it appears in qBittorrent, and verify Audiobookshelf sees it after its scan.

## MAM Cookie ID

* Log in to MAM
* Go to Username > Prefrences > Security
* Fill out your public facing IP > click 'Submit changes'
* Copy your Cookie info:  
  * "PJbv...ncimf"
  * We need to add the 'mam_id=' infront of the key and paste that whole thing in the env. Example:
  * MAM_COOKIE=mam_id=PJbv...ncimf
