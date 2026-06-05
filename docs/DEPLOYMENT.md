# MAF Docker/Dockge Deployment Notes

## Production shape

MAF should run as a small Docker service with only `/data` persisted. It does not need the Audiobookshelf library mounted because qBittorrent already downloads into the folder ABS scans.

## Sean's environment

- qBittorrent: `http://192.168.1.125:8080`
- qBit default save path: configured on Windows; leave `QB_SAVEPATH` blank.
- Audiobookshelf: `http://192.168.1.9:13378`
- ABS scans `/audiobooks`, backed by host mount `/mnt/htpcaudiobooks` in the ABS stack.

## Draft Dockge compose

```yaml
services:
  maf:
    image: seanap/maf:latest
    container_name: maf
    restart: unless-stopped
    ports:
      - "8008:8080"
    env_file:
      - .env
    volumes:
      - /opt/stacks/maf/data:/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s
```

## Draft `.env`

```env
TZ=America/New_York
DATA_DIR=/data
DISABLE_SETUP=1
LIBRARY_MODE=qbit_abs_shared
ENABLE_IMPORT=0

MAM_COOKIE=REDACTED

QB_URL=http://192.168.1.125:8080
QB_USER=
QB_PASS=
QB_SAVEPATH=
QB_CATEGORY=maf
QB_TAGS=MAM,audiobook,maf

WEDGE_MODE=smart
WEDGE_UNKNOWN_FALLBACK=true

ABS_URL=http://192.168.1.9:13378
```

## Verification before production pull

```bash
docker compose config
curl -fsS http://192.168.1.125:8080/api/v2/app/version
curl -fsS http://192.168.1.9:13378/status
```

Then deploy to Dockge as a test stack first. Add one known-safe MAM item manually, verify it appears in qBit, then verify ABS sees it after scan.

## Security warning

MAF is a control-plane service that can add torrents to qBit and stores private MAM RSS URLs. Expose only on trusted LAN/Tailscale unless an authenticated reverse proxy is added. Do not publish this raw app to the public Internet, because humans click things.
