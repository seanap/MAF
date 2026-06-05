# MAF Next-Step Development Specifications

> **For Hermes:** Use `subagent-driven-development` and `test-driven-development` before changing production code. Each step below includes acceptance criteria, adversarial review points, and verification gates.

**Scope:** Implement the six next steps identified after baseline stabilization:

1. Build proper `mam.py` and `qbit.py` adapters.
2. Change add flow to fetch `.torrent` server-side from MAM and upload bytes to qBit.
3. Add idempotent grabbed/history behavior.
4. Add smart Freeleech Wedge decision logic.
5. Add advanced M4B search preset.
6. Add RSS dashboard.

**Operator environment:** qBittorrent at `http://192.168.1.125:8080`, Audiobookshelf at `http://192.168.1.9:13378`, qBit downloads to its default Windows path, ABS scans the same backing folder. MAF must not move/copy/hardlink/organize files.

---

## Shared Architecture

### New modules

- `app/models.py` — stable DTOs and serialization helpers.
- `app/mam.py` — MAM search, torrent URL construction, torrent-byte fetch, RSS parsing helpers.
- `app/qbit.py` — qBittorrent Web API adapter.
- `app/history_store.py` — SQLite-backed idempotent history/grab/hide state.
- `app/wedge.py` — smart Freeleech Wedge policy.
- `app/presets.py` — Sean's advanced M4B MAM preset.
- `app/rss.py` — feed registry, redaction, feed item normalization.

### Endpoint additions/replacements

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
- `PATCH /api/feeds/{feed_id}`
- `DELETE /api/feeds/{feed_id}`
- `POST /api/feeds/{feed_id}/refresh`
- `GET /api/rss/items`

Legacy `/search`, `/add`, and `/history` may remain as compatibility wrappers until the UI is fully migrated, but new tests target `/api/*`.

### Common security requirements

- No API response includes `MAM_COOKIE`, qBit password, ABS token, full private RSS URL, or MAM private download URL.
- qBit URL is config-controlled; add/search endpoints do not accept arbitrary outbound URLs.
- RSS fetching is limited to saved feed URLs; add flow is by MAM torrent id/canonical key, not user-supplied URL.
- All external HTTP calls have timeouts.
- Unit tests use fake transports/monkeypatching; they do not require real MAM/qBit/ABS.

---

# Step 1 — MAM and qBit Adapters

## Goal

Create focused integration adapters that isolate MAM and qBittorrent protocol details from FastAPI route code.

## Files

- Create: `app/mam.py`
- Create: `app/qbit.py`
- Create: `app/models.py`
- Test: `tests/test_mam_client.py`
- Test: `tests/test_qbit_client.py`

## User-facing behavior

None directly. This is the foundation for safer search/add operations.

## Internal contracts

### `MamClient`

- Constructor accepts `base_url`, `cookie`, and optional async HTTP client/transport hook.
- `build_cookie(raw)` preserves upstream `mam_id`/cookie behavior.
- `build_download_url(torrent_id, use_wedge=False)` returns `/tor/download.php?tid=<id>` and appends `fl=1` only when requested.
- `fetch_torrent_bytes(torrent_id, use_wedge=False)` returns bytes and content metadata or raises a typed `MamError`.
- Rejects blank/non-numeric torrent ids.

### `QbitClient`

- Constructor accepts `base_url`, `username`, `password`, optional client.
- `login()` supports auth-bypass success and normal `Ok.` response.
- `status()` returns version, web API version, default save path, and auth-bypass flag when available.
- `add_torrent_bytes(torrent_bytes, filename, category, tags, savepath)` uploads via `/api/v2/torrents/add`.
- Omits `savepath` if `savepath` is empty.

## Acceptance criteria

- Adapter tests pass without network.
- qBit add payload omits `savepath` for empty `QB_SAVEPATH`.
- MAM download URL uses `tid`, not browser `dl` hash URLs.
- No adapter leaks cookies/passwords in exceptions.

## Adversarial review checklist

- Could a request force MAF to fetch an arbitrary URL? Must be no.
- Could a bad torrent id cause path/URL injection? Must be no.
- Could qBit upload override Sean's save path accidentally? Must be no.
- Are secrets redacted from errors/logs? Must be yes.

## Verification commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_mam_client.py tests/test_qbit_client.py -q
```

---

# Step 2 — Server-Side Torrent Fetch and qBit Upload Add Flow

## Goal

Replace add flow with backend-only MAM torrent fetch and qBit byte upload.

## Files

- Modify: `app/main.py`
- Modify/Create: `app/mam.py`
- Modify/Create: `app/qbit.py`
- Test: `tests/test_add_flow.py`

## User-facing behavior

User clicks Add/Add with Wedge. MAF fetches torrent from MAM server-side and sends bytes to qBit. qBit then uses its own default folder.

## API contract

`POST /api/torrents/add`

Request:

```json
{
  "torrent_id": "123456",
  "title": "Optional title",
  "author": "Optional author",
  "narrator": "Optional narrator",
  "use_wedge": null
}
```

Response:

```json
{
  "ok": true,
  "state": "grabbed|duplicate",
  "torrent_id": "123456",
  "wedge_used": true,
  "qbit_hash": null
}
```

## Acceptance criteria

- Add flow never sends MAM private URL to browser or qBit by default.
- Failed MAM fetch returns 502 and does not mark grabbed.
- Failed qBit upload returns 502 and does not mark grabbed.
- Empty qBit save path remains omitted.
- Legacy `/add` delegates to the same flow for compatibility.

## Adversarial review checklist

- Does qBit get torrent bytes, not a URL? Verify via tests.
- Is add idempotent if qBit says duplicate? Verify.
- Are user-supplied title/author trusted for anything dangerous? Must be display/history only.
- Does the route require cookie configured before trying MAM? Must fail safely.

## Verification commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_add_flow.py -q
```

---

# Step 3 — Idempotent Grabbed/History State

## Goal

Track grabbed/hidden/failed states so already requested books can be suppressed and duplicate clicks do not corrupt history.

## Files

- Create: `app/history_store.py`
- Modify: `app/main.py`
- Test: `tests/test_history_store.py`

## Data model

SQLite table `history_events`:

- `id INTEGER PRIMARY KEY`
- `canonical_key TEXT NOT NULL`
- `torrent_id TEXT`
- `title TEXT`
- `author TEXT`
- `narrator TEXT`
- `state TEXT NOT NULL`
- `qbit_hash TEXT`
- `wedge_used INTEGER`
- `wedge_reason TEXT`
- `error TEXT`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Unique index:

- one current event per `canonical_key` + `state` where useful; grabbed should be idempotent.

## API contract

- `GET /api/history`
- `POST /api/history/hide`
- `POST /api/history/unhide`
- `POST /api/history/mark-grabbed`

## Acceptance criteria

- `mark_grabbed` called twice for same torrent returns existing/current grabbed state, not duplicate rows.
- `is_grabbed(canonical_key)` works.
- `hide` and `unhide` update display state without deleting grabbed history.
- Add flow records grabbed only after qBit accept/duplicate.
- Search/RSS normalization can annotate items with `grabbed`/`hidden`.

## Adversarial review checklist

- Could a failed add suppress a future add? Must be no.
- Could hiding delete audit/history? Must be no.
- Does duplicate handling rely on titles? Must be no; use torrent id/canonical key.

## Verification commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_history_store.py -q
```

---

# Step 4 — Smart Freeleech Wedge Policy

## Goal

Use wedges only when useful by default, while allowing explicit override later.

## Files

- Create: `app/wedge.py`
- Modify: `app/models.py`
- Modify: `app/main.py`
- Test: `tests/test_wedge_policy.py`

## Policy

Config:

- `WEDGE_MODE=smart|always|never`
- `WEDGE_UNKNOWN_FALLBACK=true|false`

Smart mode:

- already free/VIP/sitewide/personal/FL VIP → no wedge
- normal non-free → wedge
- unknown freeleech metadata → wedge only if fallback enabled

## Acceptance criteria

- Decision has fields: `use_wedge`, `reason`, `mode`.
- Add API records `wedge_used` and `wedge_reason`.
- Explicit request `use_wedge` can override config only if route adds clear metadata; initial implementation may omit override and rely on config.
- MAM URL appends `fl=1` only when decision says yes.

## Adversarial review checklist

- Does smart mode waste wedges on already-free torrents? Must be no.
- Does unknown metadata behavior match Sean's abundant wedge preference? Default yes.
- Is decision visible/testable independent of network? Must be yes.

## Verification commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_wedge_policy.py -q
```

---

# Step 5 — Advanced M4B Search Preset

## Goal

Provide Sean's default MAM advanced M4B search preset with dynamic date windows and safe backend-controlled payload construction.

## Files

- Create: `app/presets.py`
- Modify: `app/mam.py`
- Modify: `app/main.py`
- Test: `tests/test_presets.py`
- Test: `tests/test_search_api.py`

## Preset

- text: `m4b`
- searchType: `all`
- srchIn: title, description, tags, author, narrator, series, fileTypes, filenames
- language English: `browse_lang[]=1`
- browse flags: `browseFlagsHideVsShow=0`, `browseFlags[]=32`
- sort: `snatchedDesc`
- startNumber: `0`
- categories: audiobook category id list from `MAF_SPEC.md`
- date window: default `past_4_months`

## API contract

`GET /api/presets` returns safe metadata.

`GET /api/search?q=<query>&window=past_4_months&page=0&perpage=25`

## Acceptance criteria

- Query defaults to `m4b` and can append user query safely.
- Per-page clamped to 1..100.
- Page/start offset clamped to non-negative.
- Preset payload deterministic under frozen date.
- Search endpoint returns normalized items and applies grabbed/hidden state.
- No arbitrary MAM search payload passthrough in the new API.

## Adversarial review checklist

- Can browser submit arbitrary MAM POST body? Must be no.
- Does date math cross month/year correctly? Test it.
- Does search accidentally include non-M4B by default? Payload should strongly bias/filter to M4B.

## Verification commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_presets.py tests/test_search_api.py -q
```

---

# Step 6 — RSS Dashboard

## Goal

Let Sean configure MAM RSS feeds for authors/series/narrators/custom watches, view new items, hide/grab them, and add using the same add flow.

## Files

- Create: `app/rss.py`
- Modify: `app/history_store.py`
- Modify: `app/main.py`
- Modify: `app/static/app.js`
- Modify: `app/templates/index.html`
- Test: `tests/test_rss.py`
- Test: `tests/test_rss_api.py`

## Feed model

- `id`
- `name`
- `kind`: author, series, narrator, custom
- `url_secret`
- `url_redacted`
- `enabled`
- timestamps

## API contract

- `GET /api/feeds`
- `POST /api/feeds`
- `PATCH /api/feeds/{feed_id}`
- `DELETE /api/feeds/{feed_id}`
- `POST /api/feeds/{feed_id}/refresh`
- `GET /api/rss/items`

## Acceptance criteria

- Feed URLs are redacted in API responses.
- RSS fetch happens server-side only.
- Malformed RSS items do not crash refresh.
- Items normalize to same DTO fields as search results.
- Duplicate torrent id across feeds dedupes or returns same canonical key.
- Add from RSS uses `/api/torrents/add`.
- UI initially can be functional/simple; it does not need fancy styling.

## Adversarial review checklist

- Does API leak private RSS token? Must be no.
- Can user make server fetch arbitrary URLs without saving a feed? Must be no.
- Are RSS titles escaped in UI? Must be yes.
- Does refresh failure corrupt existing items? Must be no.

## Verification commands

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_rss.py tests/test_rss_api.py -q
```

---

# Final Integration Gate

Run:

```bash
uv run --with-requirements requirements.txt --with pytest python -m pytest -q
python3 -m py_compile app/main.py app/mam.py app/qbit.py app/history_store.py app/wedge.py app/presets.py app/rss.py app/models.py
node --check app/static/app.js
docker compose config >/tmp/maf-compose-config.txt
```

Reject the release if any of these fail.

Also manually inspect:

```bash
git diff --stat
git status --short
```

Then commit using conventional commits and push to the private `seanap/MAF` repo.
