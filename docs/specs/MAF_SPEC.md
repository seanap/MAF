# MAF Modification Specification

Status: Draft v1, adversarially reviewed  
Project: `MAF`, private fork of `raygan/mam-audiofinder`  
Target user/environment: Sean's local/Tailscale audiobook workflow

## 1. Executive Summary

MAF is a lightweight remote MyAnonamouse audiobook request console. It should let Sean search or review MAM-only audiobook candidates while remote over Tailscale, then send selected torrents to qBittorrent. qBittorrent already downloads into the folder Audiobookshelf scans, so MAF must not organize files.

The correct architecture is:

1. MAF authenticates to MAM server-side.
2. MAF searches MAM or reads configured MAM RSS feeds.
3. MAF normalizes search/RSS entries into one result model.
4. MAF applies local grabbed/hidden state and smart Freeleech Wedge advisory/selection logic.
5. User clicks add.
6. MAF fetches the `.torrent` from MAM server-side.
7. MAF uploads torrent bytes to qBittorrent.
8. qBittorrent uses its own default save path.
9. Audiobookshelf scans that same backing folder and performs metadata matching.

MAF is **not** a Calibre integration, audiobook importer, metadata organizer, file mover, hardlinker, renamer, transcoder, or ABS library manager. Banana-grade scope creep goes in the airlock.

## 2. Verified Production Environment

### 2.1 Audiobookshelf

Verified from mounted Docker stack and ABS API.

- Service: Audiobookshelf
- URL: `http://192.168.1.9:13378`
- Version endpoint: `/status` reported Audiobookshelf `2.35.0`
- Docker stack path: `/mnt/dockervm/opt/stacks/abs`
- Container name: `abs`
- Image: `ghcr.io/advplyr/audiobookshelf:latest`
- Port mapping: `13378:80`
- ABS library name: `Audiobooks`
- ABS media type: `book`
- ABS library full path: `/audiobooks`
- Docker host mount from stack:
  - Host: `/mnt/htpcaudiobooks`
  - Container: `/audiobooks`

Current stack excerpt:

```yaml
services:
  audiobookshelf:
    container_name: abs
    image: ghcr.io/advplyr/audiobookshelf:latest
    ports:
      - 13378:80
    volumes:
      - /mnt/htpcaudiobooks:/audiobooks:rw,rshared
      - /opt/stacks/audiobookshelf/config:/config
      - /opt/stacks/audiobookshelf/metadata:/metadata
    environment:
      - TZ=America/New_York
    restart: unless-stopped
```

### 2.2 qBittorrent

Verified from Web API safe GETs.

- Host: Windows 11 PC
- URL: `http://192.168.1.125:8080`
- qBittorrent version: `v5.1.4`
- Web API version: `2.11.4`
- Web UI port: `8080`
- Web UI bind: `*`
- `bypass_local_auth`: `true`
- Default save path: `C:\Users\HTPC\Desktop\Audiobooks local`
- Temp path: `C:\Users\HTPC\Desktop\Audiobooks local\temp`

Production rule: leave `QB_SAVEPATH` empty unless Sean explicitly asks to override qBit. Empty means qBit uses its configured default path.

### 2.3 Target MAF Deployment

- Runs as Docker container managed by Dockge.
- Exposed over Tailscale or trusted LAN only.
- Stores only app state in `/data`.
- Does **not** need a writable mount of ABS library.
- Does **not** need qBit/ABS path mapping.
- Can optionally mount ABS library read-only later for diagnostics, but not for the initial implementation.

## 3. Product Requirements

### 3.1 Core Requirements

- Search MAM catalog specifically.
- Provide a default advanced M4B search preset matching Sean's bookmark behavior.
- Filter results to M4B-oriented audiobook candidates.
- Provide MAM RSS feed dashboard for configured author, series, narrator, and custom feeds.
- Send selected torrent to qBittorrent with one click.
- Support smart Freeleech Wedge behavior.
- Mark or hide already grabbed torrents.
- Preserve local add history and feed item state.
- Integrate with the local environment config for qBit and ABS status/verification.
- Support deployment through a private GitHub repo, Docker image, and Dockge stack.

### 3.2 Non-Requirements / Non-Goals

MAF must not:

- Integrate with Calibre.
- Move files.
- Copy files.
- Hardlink files.
- Rename files.
- Format or organize files.
- Edit metadata files.
- Transcode audio.
- Delete completed downloads.
- Import into ABS.
- Replace ABS matching/scanning.
- Become a general request platform for non-MAM sources.
- Become a generic RSS automation engine.
- Expose MAM cookies, qBit credentials, private RSS tokens, or private torrent URLs to the browser.

The current upstream import subsystem conflicts with this workflow and must be removed, hidden, or disabled before production.

## 4. MAM Search Specification

### 4.1 Advanced M4B Preset

The default preset should reproduce Sean's MAM advanced search bookmark, but with a dynamic start date.

Base intent:

- Search text: `m4b`
- Search type: `all`
- Search scope: `torrents`
- Enabled search fields:
  - title
  - description
  - tags
  - author
  - narrator
  - series
  - fileTypes
  - filenames
- Language:
  - English, MAM `browse_lang[]=1`
- Browse flags:
  - `browseFlagsHideVsShow=0`
  - `browseFlags[]=32`
- Sort:
  - `snatchedDesc`
- Start number/page offset:
  - `0`
- Unit:
  - `1`
- Categories:
  - `39`, `50`, `83`, `51`, `97`, `40`, `41`, `106`, `42`, `52`, `98`, `54`, `55`, `43`, `99`, `84`, `56`, `45`, `57`, `85`, `87`, `119`, `88`, `59`, `47`, `53`, `89`, `100`, `0`

Dynamic date modes:

- `past_3_months`
- `past_4_months` default candidate
- `past_12_months`
- explicit ISO date, e.g. `2026-01-01`

Acceptance criteria:

- Preset payload is deterministic and covered by tests.
- Date math is tested with frozen time.
- User can adjust date window without editing source.
- Backend clamps paging/per-page values.
- Backend rejects arbitrary unsupported search payload fields unless explicitly allowed.

### 4.2 Result Normalization

Every MAM search result should normalize to a common DTO:

```json
{
  "canonical_key": "mam:<torrent_id>",
  "source": "search",
  "feed_id": null,
  "mam_torrent_id": "123456",
  "title": "Book Title",
  "author": "Author Name",
  "series": "Series Name",
  "narrator": "Narrator Name",
  "format": "M4B",
  "size_bytes": 123456789,
  "seeders": 10,
  "leechers": 0,
  "uploaded_at": "2026-06-01T00:00:00Z",
  "details_url": "https://www.myanonamouse.net/t/...",
  "is_freeleech": true,
  "freeleech_reason": "vip|personal|sitewide|fl_vip|unknown|none",
  "wedge_recommended": false,
  "wedge_reason": "already_free|normal_torrent|unknown_metadata",
  "grabbed": false,
  "hidden": false
}
```

Rules:

- All raw MAM fields are untrusted.
- Result DTOs must not include cookies, private RSS tokens, or private download URLs.
- Store raw JSON only if secrets are stripped.

## 5. RSS Dashboard Specification

### 5.1 Feed Configuration

Supported feed kinds:

- `author`
- `series`
- `narrator`
- `custom`

Feed fields:

- `id`
- `name`
- `kind`
- `url`
- `enabled`
- timestamps

Security rule: RSS URLs may contain private tracker tokens. Store them as secrets and never expose full URLs back to the browser after save. UI should show name, kind, enabled state, and redacted URL summary.

### 5.2 Feed Item Behavior

- Fetch feeds server-side only.
- Normalize RSS items into the same DTO shape as search results.
- Deduplicate by MAM torrent id when available.
- If RSS does not provide enough freeleech metadata, optionally enrich by MAM torrent id/search detail.
- Apply grabbed/hidden state before display.
- Default dashboard hides grabbed items, with a toggle to show them.
- Manual refresh first. Scheduled polling can be a later phase.

Acceptance criteria:

- Malformed RSS item does not crash dashboard.
- Private feed URL is redacted in API/UI/logs.
- Same torrent appearing in multiple feeds appears as one candidate or clearly grouped duplicate.
- Add from RSS uses the same qBit and wedge logic as add from search.

## 6. Smart Freeleech Wedge Policy

### 6.1 Source Behavior Confirmed from Seshat Reference

Seshat builds MAM torrent download URLs as:

```text
https://www.myanonamouse.net/tor/download.php?tid=<torrent_id>
```

When using a Freeleech Wedge, Seshat appends:

```text
&fl=1
```

Seshat's normal policy does not blindly wedge everything. It avoids spending wedges on torrents already free by VIP/global/sitewide/personal freeleech/FL VIP flags, and uses wedges for non-free torrents when policy permits.

### 6.2 MAF Default Policy

Config:

```env
WEDGE_MODE=smart
WEDGE_UNKNOWN_FALLBACK=true
```

Decision matrix:

- Already VIP/free/sitewide freeleech/personal freeleech/FL VIP:
  - `wedge_recommended=false`
  - Do not append `fl=1`.
- Normal non-free torrent:
  - `wedge_recommended=true`
  - Append `fl=1` when fetching torrent if user selected smart wedge add.
- Unknown metadata:
  - If `WEDGE_UNKNOWN_FALLBACK=true`, use wedge because Sean has abundant wedges.
  - If false, warn and do not wedge by default.

Important: wedge behavior should be visible in UI before add. The Add button can say `Add`, `Add with Wedge`, or show a badge such as `Wedge recommended: normal non-free torrent`.

Acceptance criteria:

- Tests cover already-free, normal non-free, and unknown metadata cases.
- Force-wedge manual override, if added, must be visually explicit and not the default.
- Wedge decision is recorded in add history.
- MAF never appends `fl=1` for already-free torrents in smart mode.

## 7. qBittorrent Integration Specification

### 7.1 qBit Adapter

MAF should use a dedicated qBit adapter module.

Responsibilities:

- Check qBit connectivity:
  - `/api/v2/app/version`
  - `/api/v2/app/webapiVersion`
  - `/api/v2/app/preferences`
- Support qBit v5.1.4 / Web API 2.11.4.
- Handle local auth bypass and explicit login credentials.
- Add torrents using server-fetched torrent bytes, not browser-provided private URLs.
- Apply configured category/tags.
- Leave save path unset when `QB_SAVEPATH` is empty.
- Treat duplicate torrent response as idempotent/already-added where possible.

Production config:

```env
QB_URL=http://192.168.1.125:8080
QB_SAVEPATH=
QB_CATEGORY=maf
QB_TAGS=MAM,audiobook,maf
```

Recommended optional tags per torrent:

- `MAM`
- `audiobook`
- `maf`
- `mamid-<id>` or equivalent if qBit accepts static string tag format

### 7.2 Add Flow

1. Client sends canonical item id/torrent id to backend.
2. Backend checks local history/qBit duplicate state.
3. Backend decides wedge usage according to policy.
4. Backend fetches `.torrent` from MAM with cookie server-side.
5. Backend uploads torrent bytes to qB `/api/v2/torrents/add`.
6. Backend records history only after qB accepts or reports duplicate.
7. Backend returns sanitized status.

Acceptance criteria:

- qBit receives torrent bytes, not private MAM URL by default.
- Empty `QB_SAVEPATH` omits save path field or sends no override.
- Failed MAM fetch does not mark grabbed.
- Failed qBit upload does not mark grabbed.
- Duplicate add does not create duplicate history.

## 8. Audiobookshelf Integration Specification

### 8.1 Required Integration

None for file handling. ABS is already correctly configured to scan `/audiobooks`.

MAF should document and verify only:

- ABS reachable at configured URL.
- ABS library exists.
- ABS library folder is `/audiobooks`.

### 8.2 Optional Later Integration

Optional read-only/status features:

- ABS connectivity status card.
- Display library name/folder from ABS API.
- Optional manual `trigger scan` button if ABS API supports it and Sean wants it.
- Optional library existence check for already-owned items, only if reliable.

Non-negotiable: no ABS import/copy/move logic.

## 9. Security Requirements

### 9.1 Current Upstream Risks

The upstream app has no authentication and exposes sensitive control endpoints. It can currently:

- Write setup config.
- Change qBit target URL.
- Add torrents.
- List qBit torrents.
- Import/copy/move/hardlink files.
- Delete local history.

This is acceptable only as a prototype. Production MAF needs guardrails, because humans keep attaching networks to other networks and acting surprised.

### 9.2 Required Controls

- Production examples set `DISABLE_SETUP=1`.
- Setup API disabled or authenticated before production.
- App must not expose secrets in status/setup responses.
- `QB_URL` must be configured, not user-controlled per request.
- If setup remains, validate `QB_URL` against an allowlist.
- RSS URL fields are treated as secrets.
- MAM cookie is treated as secret.
- Browser never receives MAM cookie or private download URLs.
- Logs redact cookies, passwords, tokens, RSS tokens, and secret-bearing URLs.
- Remove/disable arbitrary filesystem operations.
- Escape all MAM/RSS content in frontend.

Recommended production exposure:

- Tailscale-only binding or trusted LAN only.
- If exposed beyond trusted tailnet/LAN, add app auth or place behind an authenticated reverse proxy.
- Consider restricting Windows firewall for qBit WebUI `8080` to Docker VM and trusted clients.

## 10. Data Model

### 10.1 Tables

#### `schema_meta`

- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`

#### `feeds`

- `id INTEGER PRIMARY KEY`
- `name TEXT NOT NULL`
- `kind TEXT NOT NULL`
- `url_secret TEXT NOT NULL`
- `url_redacted TEXT NOT NULL`
- `enabled INTEGER NOT NULL DEFAULT 1`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

#### `items`

- `id INTEGER PRIMARY KEY`
- `source TEXT NOT NULL`
- `source_feed_id INTEGER NULL`
- `mam_torrent_id TEXT NULL`
- `canonical_key TEXT NOT NULL UNIQUE`
- `title TEXT NOT NULL`
- `author TEXT NULL`
- `series TEXT NULL`
- `narrator TEXT NULL`
- `format TEXT NULL`
- `size_bytes INTEGER NULL`
- `seeders INTEGER NULL`
- `leechers INTEGER NULL`
- `is_freeleech INTEGER NULL`
- `freeleech_reason TEXT NULL`
- `wedge_recommended INTEGER NULL`
- `wedge_reason TEXT NULL`
- `uploaded_at TEXT NULL`
- `details_url TEXT NULL`
- `raw_json TEXT NULL`
- `first_seen_at TEXT NOT NULL`
- `last_seen_at TEXT NOT NULL`

#### `history`

- `id INTEGER PRIMARY KEY`
- `canonical_key TEXT NOT NULL`
- `mam_torrent_id TEXT NULL`
- `state TEXT NOT NULL`
  - `grabbed`
  - `hidden`
  - `ignored`
  - `failed`
- `qbit_hash TEXT NULL`
- `wedge_used INTEGER NULL`
- `wedge_reason TEXT NULL`
- `error TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

#### `add_attempts`

- `id INTEGER PRIMARY KEY`
- `canonical_key TEXT NOT NULL`
- `mam_torrent_id TEXT NULL`
- `status TEXT NOT NULL`
  - `started`
  - `accepted`
  - `duplicate`
  - `failed`
- `qbit_hash TEXT NULL`
- `wedge_used INTEGER NULL`
- `error TEXT NULL`
- `created_at TEXT NOT NULL`

### 10.2 State Rules

- `grabbed` means MAF believes qBit accepted the torrent or qBit reported duplicate.
- `hidden` means suppress from default UI.
- `failed` records an attempted add failure and should not suppress future add by default.
- Same `canonical_key` should not create contradictory duplicate grabbed rows.

## 11. API Specification

### 11.1 UI Routes

- `GET /`
  - Main dashboard.
- `GET /setup`
  - Optional setup route, disabled in production.
- `GET /health`
  - Minimal health response. No secrets.

### 11.2 Config/Status APIs

- `GET /api/status`
  - Returns redacted app, qBit, and optional ABS status.
- `POST /api/setup`
  - Disabled when `DISABLE_SETUP=1`.
  - Authenticated/allowlisted if enabled.

### 11.3 Search APIs

- `GET /api/search`
  - Runs search using default preset plus user query/date/window/page.
- `GET /api/presets`
  - Lists available search presets and date window options.

### 11.4 RSS APIs

- `GET /api/feeds`
- `POST /api/feeds`
- `PATCH /api/feeds/{feed_id}`
- `DELETE /api/feeds/{feed_id}`
- `POST /api/feeds/{feed_id}/refresh`
- `GET /api/rss/items`

### 11.5 Torrent APIs

- `POST /api/torrents/add`
  - Adds by canonical item or MAM torrent id.
- `GET /api/qbit/status`
  - Sanitized qBit status.

### 11.6 History APIs

- `GET /api/history`
- `POST /api/history/hide`
- `POST /api/history/unhide`
- `POST /api/history/mark-grabbed`
- `DELETE /api/history/{id}`

### 11.7 Removed/Disabled APIs

- `/import`
- Any API that copies, moves, links, deletes, or mutates audiobook files.
- Any API that accepts arbitrary fetch URLs.

## 12. Implementation Plan

### Phase 0 — Repo and Baseline

- Clone upstream `raygan/mam-audiofinder` into `/home/hermes/projects/MAF`.
- Rename upstream remote to `upstream`.
- Create private GitHub repo `MAF`.
- Add spec and local project docs.
- Establish branch protection/review workflow if desired.

Exit criteria:

- Private repo exists.
- Baseline pushed.
- Spec committed.

### Phase 1 — Test Harness and Config Stabilization

- Add pytest.
- Add temp DB/data-dir support.
- Replace hardcoded `sqlite:////data/history.db` with configurable DB path.
- Move DB init out of import-time hard failure path or ensure directories are created safely.
- Add config redaction helpers.
- Add compose defaults or a production compose template.

Tests:

- App imports with temp DB path and no `/data`.
- `py_compile` passes.
- Config loads defaults.
- Secrets redact.
- `DISABLE_SETUP` disables setup routes.

### Phase 2 — Remove/Disable Import Subsystem

- Remove import UI or hide it under a disabled feature flag.
- Disable `/import` and file operation routes.
- Remove `DL_DIR`, `LIB_DIR`, `IMPORT_MODE`, `QB_PATH_MAP` from production docs unless retained only for upstream compatibility notes.
- Ensure no move/copy/hardlink code path is reachable.

Tests:

- `/import` returns `404`, `410`, or disabled response.
- No file-operation endpoint is active.
- UI contains no import action in MAF mode.

### Phase 3 — qBit Adapter and Idempotent Add

- Implement `qbit.py` adapter.
- Support qBit v5.1.4 / Web API 2.11.4.
- Add torrent bytes upload flow.
- Add duplicate handling.
- Add local history state.

Tests:

- Empty `QB_SAVEPATH` omits savepath.
- Non-empty `QB_SAVEPATH` sends exact configured string.
- Duplicate qBit response is idempotent.
- qBit failure does not mark grabbed.

### Phase 4 — MAM Client, Preset Search, and Wedge Policy

- Implement MAM client module.
- Implement advanced M4B preset and dynamic start date.
- Normalize search results.
- Implement smart wedge policy.
- Server-side torrent fetch with optional `fl=1` only when policy says.

Tests:

- Preset payload matches expected fields.
- Dynamic dates compute correctly.
- Already-free torrents do not use wedge.
- Normal non-free torrents use wedge in smart mode.
- Unknown metadata uses wedge only when fallback enabled.
- Browser/API never receives private download URL.

### Phase 5 — RSS Dashboard

- Add feed model/endpoints.
- Add server-side feed fetching.
- Normalize RSS entries.
- Add feed dashboard UI.
- Add hide/grabbed controls.

Tests:

- Feed URL redacted.
- Malformed item handled safely.
- Duplicate item across feeds dedupes or groups correctly.
- Add from RSS uses same add pipeline as search.

### Phase 6 — Production Packaging

- Add Dockerfile/compose release verification.
- Add GitHub Actions or local build script for Docker image.
- Push to Docker Hub under Sean's chosen namespace/repo.
- Write Dockge production stack docs.
- Deploy first as test stack, then production.

Exit criteria:

- Test suite passes.
- Docker image builds.
- Test container can reach qBit and ABS status endpoints.
- One safe manual MAM add is verified end-to-end.
- Dockge production stack uses released image.

## 13. Test and Verification Matrix

### 13.1 Automated Tests

- Config:
  - app imports without `/data`
  - `DATA_DIR`/`DB_PATH` honored
  - secret redaction
  - setup disabled behavior
- MAM:
  - cookie formatting
  - advanced search payload
  - RSS parsing
  - torrent fetch allowlist
  - wedge URL behavior
- qBit:
  - version/status parsing
  - auth bypass compatibility
  - add torrent bytes
  - savepath omission
  - duplicate handling
- History:
  - grabbed state
  - hidden state
  - failed state
  - idempotent add
- Frontend/API safety:
  - XSS escaping for title/author/narrator/feed names
  - no secret leakage
  - malformed upstream data handled
- Removed behavior:
  - import endpoint disabled
  - no copy/move/hardlink API reachable

### 13.2 Manual Environment Verification

From Docker VM or trusted shell:

```bash
curl -fsS http://192.168.1.125:8080/api/v2/app/version
curl -fsS http://192.168.1.125:8080/api/v2/app/webapiVersion
curl -fsS http://192.168.1.9:13378/healthcheck
curl -fsS http://192.168.1.9:13378/status
```

Expected:

- qBit version `v5.1.4`
- Web API `2.11.4`
- ABS health OK
- ABS status returns server JSON

After MAF deploy:

```bash
curl -fsS http://<maf-host>:8008/health
```

Expected:

```json
{"ok":true}
```

End-to-end test:

1. Search MAM for a harmless known audiobook candidate.
2. Add one torrent.
3. Verify qBit receives torrent.
4. Verify qBit save path remains default.
5. Verify ABS sees item after scan.
6. Verify MAF marks item grabbed.
7. Verify same item is hidden/disabled on subsequent search/feed view.

## 14. Production Dockge Template

Draft production compose after MAF fork supports no-import mode:

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
      - ${DATA_DIR:-/opt/stacks/maf/data}:/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s
```

Draft `.env`:

```env
DATA_DIR=/opt/stacks/maf/data
TZ=America/New_York
DISABLE_SETUP=1

MAM_COOKIE=[REDACTED]

QB_URL=http://192.168.1.125:8080
QB_USER=[REDACTED_OR_EMPTY_IF_AUTH_BYPASS_WORKS]
QB_PASS=[REDACTED_OR_EMPTY_IF_AUTH_BYPASS_WORKS]
QB_SAVEPATH=
QB_CATEGORY=maf
QB_TAGS=MAM,audiobook,maf

WEDGE_MODE=smart
WEDGE_UNKNOWN_FALLBACK=true
DEFAULT_HIDE_GRABBED=true
DEFAULT_SEARCH_PRESET=recent_m4b_snatched
DEFAULT_SEARCH_WINDOW=past_4_months

ABS_URL=http://192.168.1.9:13378
ABS_TOKEN=[REDACTED_OPTIONAL]
ABS_LIBRARY_ID=5d457c9e-e177-4720-a5e7-a608c6e7a18d
```

Notes:

- `ABS_TOKEN` is optional unless implementing ABS status/scan features.
- Do not mount `/mnt/htpcaudiobooks` unless adding read-only diagnostics.
- Keep setup disabled in production because upstream has no auth.

## 15. Adversarial Release Rejection Checklist

Reject release if any item is true:

- Import UI remains active.
- `/import` remains reachable in production mode.
- MAF can move/copy/hardlink/delete audiobook files.
- MAF requires `QB_SAVEPATH` for Sean's environment.
- Empty `QB_SAVEPATH` sends an invalid path override.
- Browser receives MAM cookie, private RSS URL, private torrent URL, qBit password, or API token.
- Logs print secrets.
- Setup API is reachable when `DISABLE_SETUP=1`.
- User-controlled request can make MAF fetch arbitrary URLs.
- MAM/RSS title with `<script>` executes in browser.
- Duplicate add creates duplicate/conflicting history.
- Failed qBit add marks item grabbed.
- App fails to import/start solely because `/data` is missing during tests.
- Tests require real MAM or real qBit in CI/unit tests.
- Docker/Dockge docs include file organization assumptions from upstream.
- Docker image cannot be rebuilt reproducibly.

## 16. Current Baseline Findings

Verified locally against cloned upstream:

- Repo cloned to `/home/hermes/projects/MAF`.
- Upstream remote renamed to `upstream`.
- Python compile check for `app/main.py` passes.
- App import fails on host without `/data` because SQLite path is hardcoded to `/data/history.db` and initialized at import time.
- `docker compose config` fails without `.env` because `${DATA_DIR}` and `${MEDIA_ROOT}` expand empty.
- Docker build could not be run from Hermes user due Docker socket permission.
- No existing test suite found.
- Current code contains import/path-mapping subsystem that conflicts with Sean's desired architecture.
- Current app has no built-in auth.

## 17. Immediate Next Actions

1. Commit this spec as the project control document.
2. Create private GitHub repo `MAF` and push baseline/spec.
3. Implement Phase 1 test harness and configurable DB path.
4. Disable/remove import subsystem.
5. Build qBit/MAM adapters under tests.
6. Add RSS/search dashboard and smart wedge policy.
7. Build Docker image and deploy test stack before production Dockge pull.

Trust the awesomeness, but verify the backup.
