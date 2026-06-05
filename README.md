# MAF — MAM Audiobook Finder

Private fork for Sean's MAM-only audiobook request workflow.

MAF searches MyAnonamouse, monitors configured MAM RSS feeds, applies smart Freeleech Wedge policy, and sends server-fetched `.torrent` bytes to qBittorrent. qBittorrent downloads to its own configured default folder; Audiobookshelf scans that same backing folder and handles matching/metadata.

## What MAF is

- Remote MAM search/request console for Tailscale/LAN use.
- MAM advanced M4B search preset.
- MAM RSS watch dashboard for authors, series, narrators, and custom MAM feeds.
- qBittorrent Web API sender.
- Local grabbed/hidden history so already requested items can be suppressed.
- Smart Freeleech Wedge policy.

## What MAF is not

- Not Calibre integration.
- Not an Audiobookshelf importer.
- Not a file organizer.
- Not a mover/copier/hardlinker/renamer/transcoder.
- Not a public Internet service.

## Project documentation

- [Full MAF spec](docs/specs/MAF_SPEC.md)
- [Next-step development specs](docs/specs/NEXT_STEPS_DEVELOPMENT_SPECS.md)
- [Adversarial review findings](docs/specs/ADVERSARIAL_REVIEW_NEXT_STEPS.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Deployment notes](docs/DEPLOYMENT.md)

## Runtime configuration

```env
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

Leave `QB_SAVEPATH` blank for Sean's setup so qBit uses its Windows default save path.

## Local development

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest -q
python3 -m py_compile app/main.py app/mam.py app/qbit.py app/history_store.py app/wedge.py app/presets.py app/rss.py app/models.py
node --check app/static/app.js
docker compose config >/tmp/maf-compose-config.txt
```

## Security notes

MAF stores private MAM cookies/RSS URLs and can add torrents to qBittorrent. Run it only on trusted LAN/Tailscale unless you put real authentication in front of it. API responses and UI must never expose MAM cookies, private RSS URLs, qBit passwords, ABS tokens, or private MAM download URLs.
