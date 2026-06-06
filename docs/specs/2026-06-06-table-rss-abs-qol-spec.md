# MAF Table, Default Advanced Search, RSS Dashboard, and ABS History Links Specification

> **For Hermes:** Use `subagent-driven-development` if executing this plan task-by-task. Do not implement until this spec has been reviewed against Sean's actual workflow and the live MAF codebase.

**Goal:** Make MAF feel like a practical remote MAM request console: Excel-style sortable/filterable tables, blank-search defaulting to Sean's 3-month advanced MAM search, RSS watch dashboard quality-of-life controls, and History links to both MAM and Audiobookshelf.

**Architecture:** Keep MAF boring and maintainable: FastAPI backend, SQLite-backed server state, no frontend framework, no Calibre dependency, no file organization workflow. Search/add stays MAM -> qBittorrent; ABS is used only for metadata/link visibility after ABS scans the qBit download folder.

**Tech Stack:** Python/FastAPI, SQLite, vanilla HTML/CSS/JS, qBittorrent Web API, optional Audiobookshelf HTTP API integration.

---

## 0. Current State Summary

Current relevant implementation:

- Backend:
  - `app/main.py`
    - `/api/search`: MAM search wrapper using `build_m4b_search_payload()`.
    - `/api/feeds`: list/create feeds.
    - `/api/feeds/{feed_id}`: patch/delete feeds.
    - `/api/rss/items`: list RSS items.
    - `/api/history`: list grabbed/hidden history rows.
    - `/api/torrents/add`: fetch MAM torrent and send bytes to qBittorrent.
  - `app/presets.py`: currently builds an M4B-focused search payload.
  - `app/rss.py`: stores feed definitions and feed items in SQLite.
  - `app/history_store.py`: stores grabbed/hidden item state.
- Frontend:
  - `app/templates/index.html`: one search table, RSS dashboard, History table.
  - `app/static/app.js`: search rendering, feed rendering, History rendering.
- Existing tests:
  - `tests/test_presets.py`
  - `tests/test_api_flows.py`
  - `tests/test_mam_client.py`
  - `tests/test_rss.py`

Known user workflow constraints:

- MAM is the only content source.
- qBittorrent downloads to its normal/default folder.
- Audiobookshelf scans that folder and does matching/metadata.
- MAF must **not** become a Calibre/file-organization/import tool.
- Remote access is expected over Tailscale.
- Secrets must stay server-side and redacted.

---

## 1. Requirements

### 1.1 Excel-style Search Table

Sean wants the search results table to behave more like an Excel table:

- Click headers to sort.
- Header controls provide dynamic filter menus.
- Filters should be derived from the currently loaded result set, not hard-coded.
- Sorting is currently not trustworthy and must be fixed.
- The table should support both search results and, where sensible, RSS result lists using shared table utilities.

### 1.2 Blank Search Uses Sean's 3-Month Advanced MAM Search

When the search box is blank and the user submits:

- MAF must run Sean's known advanced MAM search preset.
- It must default to a **3-month** window.
- It must preserve the intent of the original MAM bookmark advanced search:
  - text: `m4b`
  - search type: `all`
  - search scope: `torrents`
  - search fields from the bookmark:
    - title
    - description
    - tags
    - author
    - narrator
    - series
    - fileTypes
    - filenames
  - English language (`browse_lang[]=1`)
  - browse flags: `browseFlagsHideVsShow=0`, `browseFlags[]=32`
  - categories from existing MAF spec:
    - `39`, `50`, `83`, `51`, `97`, `40`, `41`, `106`, `42`, `52`, `98`, `54`, `55`, `43`, `99`, `84`, `56`, `45`, `57`, `85`, `87`, `119`, `88`, `59`, `47`, `53`, `89`, `100`, `0`
  - default sort: `snatchedDesc` unless user selects another sort.
- Non-blank searches may use a narrower, less noisy search profile if that produces better direct matches.

### 1.3 RSS Watch Dashboard Quality-of-Life

The RSS dashboard needs to mature from a debug table into an operating surface:

- Rename a feed.
- Edit a feed URL/kind/name/color/enabled state.
- Delete a feed only with deliberate UI action.
- Collapse/expand a feed.
- Limit displayed results, default `15`.
- Assign a very light row background color per feed.
- Toggle whether a feed's results are visible in the combined list.
- Toggle whether a feed is enabled for refresh.
- Preserve RSS secrets: full feed URL is never rendered back to the browser if it contains private token material. Display only redacted URL.

### 1.4 History Links to MAM and Audiobookshelf

History should show two separate link actions:

- MAM link: existing torrent details page.
- ABS link: Audiobookshelf book/item page, if known.

Because ABS scans qBittorrent's folder after MAF sends the torrent, MAF may not know the ABS item immediately. Therefore:

- Add support for storing an optional `abs_item_id` and `abs_item_url` on grabbed History rows.
- If ABS API/token/library config is available, provide a backend resolver to try to match grabbed books to ABS after scan.
- If no ABS match is known, History should show a disabled/muted ABS indicator or a link to an ABS search page if a reliable search URL exists.
- Do not block add-to-qBit on ABS resolution.

---

## 2. Non-Goals

Do **not** add:

- Calibre support.
- File renaming/reformatting/organization.
- Moving/importing into ABS.
- A separate torrent client integration beyond qBittorrent.
- Browser-side storage of MAM cookies/RSS secrets/ABS tokens.
- A frontend framework unless the user explicitly authorizes a larger UI rewrite.

---

## 3. Data Model Changes

### 3.1 Feed Table Migration

Modify `app/rss.py` schema migration logic so existing SQLite databases gain new nullable columns without data loss.

Add to `feeds`:

- `color TEXT DEFAULT '#eef6ff'`
  - Must be a safe hex color: `#RRGGBB` only.
  - Default should be a very light, non-annoying color.
- `collapsed INTEGER DEFAULT 0`
  - UI preference for whether a feed's own item group is collapsed.
- `show_in_combined INTEGER DEFAULT 1`
  - Whether this feed's RSS items appear in the combined RSS item list.
- `display_limit INTEGER DEFAULT 15`
  - Clamp server-side to `1..500`; frontend defaults to 15.

Optional but useful:

- `last_refresh_status TEXT DEFAULT ''`
- `last_refresh_message TEXT DEFAULT ''`
- `last_refresh_at TEXT DEFAULT ''`

### 3.2 RSS Item DTO Enrichment

When returning `/api/rss/items`, include feed metadata required for combined display:

```json
{
  "id": 123,
  "feed_id": 1,
  "feed_name": "Dungeon Crawler Carl",
  "feed_color": "#fff7e6",
  "feed_enabled": true,
  "feed_show_in_combined": true,
  "canonical_key": "mam:torrent:1246262",
  "torrent_id": "1246262",
  "title": "A Parade of Horribles By Matt Dinniman",
  "details_url": "https://www.myanonamouse.net/t/1246262",
  "grabbed": false,
  "hidden": false
}
```

### 3.3 History Store Migration

Modify `app/history_store.py` schema migration logic to add:

- `abs_item_id TEXT DEFAULT ''`
- `abs_item_url TEXT DEFAULT ''`
- `abs_resolved_at TEXT DEFAULT ''`
- `abs_match_status TEXT DEFAULT ''`
  - values: `''`, `pending`, `matched`, `not_found`, `ambiguous`, `error`

Do **not** store ABS tokens in History.

---

## 4. Backend API Specification

### 4.1 Search Endpoint

Current: `GET /api/search?q=&window=&page=&perpage=&sort=`

Update behavior:

- If `q.strip()` is empty:
  - Use mode `default_advanced_3mo`.
  - Query text should be `m4b`.
  - Window should default to `past_3_months` unless explicitly overridden.
  - Search fields should match Sean's bookmark fields.
- If `q.strip()` is non-empty:
  - Use mode `targeted_query`.
  - Query text should be the user's text, not `m4b <query>`.
  - Use focused fields by default: title, author, narrator, series.
  - Keep M4B filtering server-side.
- Sort must be sent to MAM as the actual selected `sortType`.
- Response must include enough metadata for debugging UI sort issues:

```json
{
  "items": [],
  "page": 0,
  "perpage": 100,
  "total": 42,
  "shown": 25,
  "preset": "default_advanced_3mo",
  "window": "past_3_months",
  "sort": "snatchedDesc",
  "query_text": "m4b",
  "search_fields": ["title", "description", "tags", "author", "narrator", "series", "fileTypes", "filenames"]
}
```

Acceptance criteria:

- Blank search returns recent M4B-like items from the last 3 months.
- Blank search does not accidentally become all-time.
- Non-blank `bobiverse` search still returns Bobiverse M4B results.
- Sort parameter survives the full path: UI -> `/api/search` query param -> MAM payload -> response metadata -> rendered sort state.

### 4.2 Feed Patch Endpoint

Current: `PATCH /api/feeds/{feed_id}` accepts `name`, `kind`, `url`, `enabled`.

Extend request model:

```json
{
  "name": "Dungeon Crawler Carl",
  "kind": "series",
  "url": "https://02e0d.mrd.ninja/rss/...",
  "enabled": true,
  "color": "#fff7e6",
  "collapsed": false,
  "show_in_combined": true,
  "display_limit": 15
}
```

Rules:

- `name` cannot be empty.
- `kind` must be `author`, `series`, `narrator`, or `custom`.
- `url`, if supplied, must pass existing MAM RSS URL validation.
- `color` must match `^#[0-9A-Fa-f]{6}$`.
- `display_limit` clamps to `1..500`.
- `url_secret` must never appear in public response JSON.

### 4.3 RSS Items Endpoint

Current: `GET /api/rss/items?feed_id=`

Extend parameters:

- `feed_id: optional int`
- `combined: bool = true`
- `include_hidden: bool = false`
- `include_grabbed: bool = false`
- `limit: int | None = None`

Behavior:

- If `combined=true`, only include feeds where `show_in_combined=1`.
- If `feed_id` is supplied, return only that feed regardless of `show_in_combined`.
- Apply per-feed `display_limit` by default when combined.
- If global `limit` is supplied, clamp to `1..500` and apply after feed filtering.
- Always annotate with grabbed/hidden state.

### 4.4 ABS Resolve Endpoint

Add optional endpoint:

`POST /api/history/{row_id}/resolve-abs`

Behavior:

- Reads History row title/author/narrator/torrent id.
- If ABS config is incomplete, returns:

```json
{"ok": false, "status": "not_configured"}
```

- If configured, query Audiobookshelf API for likely book matches.
- Candidate ABS config:
  - `ABS_URL` existing setting.
  - `ABS_TOKEN` new optional secret setting/env/config field.
  - `ABS_LIBRARY_ID` optional but recommended.
- Matching strategy:
  1. Search title.
  2. Prefer media type `book`.
  3. Prefer author match if present.
  4. If exactly one high-confidence match, store `abs_item_id`, `abs_item_url`, `abs_match_status='matched'`.
  5. If multiple plausible matches, store `abs_match_status='ambiguous'` and do not guess.
  6. If none, store `abs_match_status='not_found'`.
- Do not mutate qBittorrent or files.

ABS URL format:

- Must be confirmed during implementation against the deployed ABS version.
- Likely frontend item URL shape should be treated as a verified implementation detail, not guessed blindly.
- If the direct item URL format cannot be verified, use a safe ABS search link as fallback.

---

## 5. Frontend UX Specification

### 5.1 Shared Excel-Style Table Controller

Create a small vanilla JS table helper, probably in `app/static/table.js`, or keep in `app/static/app.js` if still compact.

Features:

- Column definitions:

```js
{
  key: 'seeders',
  label: 'Seeders',
  type: 'number',
  sortable: true,
  filter: 'checkbox',
  getValue: row => row.seeders ?? 0,
  render: row => `${row.seeders ?? '-'} / ${row.leechers ?? '-'}`
}
```

- Sort behavior:
  - Clicking header cycles: unsorted -> ascending -> descending -> unsorted.
  - Numeric sort for size/seeders/leechers.
  - Date sort for uploaded/seen dates.
  - Text sort using case-insensitive locale compare.
  - Current sort indicator: `▲`, `▼`, or muted unsorted icon.
- Filter behavior:
  - Each filterable header has a small menu button.
  - Menu contains:
    - search-within-filter input for long value lists
    - Select all
    - Clear
    - checkbox list of unique visible values
  - Filter options are generated from the **loaded dataset**.
  - Multiple filters combine with AND.
  - Multiple checked values within one column combine with OR.
  - Empty/null values represented as `(blank)`.
- Accessibility:
  - Menus close on Escape and outside click.
  - Buttons have labels/titles.
- Persistence:
  - Optional localStorage for table UI state is allowed only for non-secret preferences: sort/filter/display limits/collapsed state.
  - Do not store MAM/ABS/qBit secrets in localStorage.

### 5.2 Search Results Table

Columns:

- Title
- Author
- Series
- Narrator
- Filetype
- Size
- Seeders/Leechers
- Uploaded
- MAM Link
- Add

Default state:

- Filetype filter defaults to `m4b` when available.
- Sort defaults to backend order for blank advanced search, unless user clicks a header.
- If user selects external sort dropdown, it should either:
  - trigger a new backend search with MAM sort, or
  - be removed in favor of header sorting.

Decision:

- Prefer removing the separate sort dropdown once header sort works, to avoid conflicting sort semantics.
- If kept, label it clearly as `MAM sort` and use header sort as `table sort`.

### 5.3 Blank Search UX

When user submits with blank search box:

- Status text should say:

`Running default 3-month MAM M4B search...`

- Search box can remain blank.
- Window selector should visibly show `Past 3 months` or the UI should show a preset chip:

`Preset: Default 3-month M4B search`

This avoids the user wondering why results appeared from an empty query.

### 5.4 RSS Dashboard UX

Split RSS dashboard into two visible sections:

#### Feed Configuration Table

Columns:

- Color swatch/input
- Name
- Kind
- URL redacted
- Enabled refresh toggle
- Show in combined toggle
- Collapsed toggle
- Display limit
- Refresh button
- Edit button
- Delete button

Editing:

- Inline editing is acceptable.
- Better UX: `Edit` opens an inline expanded row with all editable fields and Save/Cancel.
- URL field should be blank by default in edit mode with placeholder:

`Paste new URL only if changing it; current secret URL remains stored.`

This prevents accidentally exposing or overwriting private RSS URLs.

Delete:

- Require a confirmation prompt containing feed name.
- Delete should remove feed definition and associated rss_items for that feed, or explicitly document if items remain orphaned. Prefer cascade delete.

#### Combined RSS Items Table

Columns:

- Feed
- Title
- Seen/Updated
- MAM Link
- Add
- Hide

Behavior:

- Row background is feed color at low opacity/lightened value.
- Results default to 15 per feed.
- Hidden/grabbed items omitted by default.
- Feed visibility toggle immediately updates combined list.
- If a feed is collapsed, its per-feed group is hidden, but combined visibility is controlled separately by `show_in_combined`.

### 5.5 History Table UX

Columns:

- Title
- Author
- Narrator
- MAM
- ABS
- When
- Status
- Remove

ABS link states:

- Matched: clickable `ABS` link.
- Pending/not configured: muted `ABS` text with title explaining status.
- Ambiguous: muted `ABS?` with optional Resolve button if implemented.
- Not found: muted `Not in ABS`.

Add optional button:

- `Resolve ABS` per row, if ABS config exists and no match is stored.

---

## 6. Implementation Plan

### Phase 1: Backend Search Preset and Sort Contract

Files:

- Modify: `app/presets.py`
- Modify: `app/main.py`
- Tests: `tests/test_presets.py`, `tests/test_api_flows.py`

Tasks:

1. Add two payload builders or a single mode-aware builder:
   - `build_default_advanced_m4b_payload(window='past_3_months', sort='snatchedDesc', ...)`
   - `build_targeted_m4b_search_payload(q, window='all', sort='snatchedDesc', ...)`
2. Ensure blank `/api/search?q=` uses default 3-month advanced preset.
3. Ensure non-blank search uses targeted preset.
4. Include `preset`, `query_text`, `search_fields`, `sort`, and `window` metadata in response.
5. Add tests proving blank search sends `text='m4b'`, bookmark fields, `startDate` for 3 months, and selected sort.
6. Add tests proving non-blank search sends user query text and focused fields.

Validation commands:

```bash
uv run --python /home/hermes/.local/bin/python3.11 --with-requirements requirements.txt --with pytest python -m pytest tests/test_presets.py tests/test_api_flows.py -q
```

Manual checks:

```bash
curl -fsS 'http://127.0.0.1:8008/api/search?q=&perpage=25' | jq '.preset,.window,.query_text,.search_fields,.items|length'
curl -fsS 'http://127.0.0.1:8008/api/search?q=bobiverse&sort=seedersDesc&perpage=25' | jq '.sort,.items[0:3][] | {title,seeders,format}'
```

### Phase 2: Backend Feed QoL Data Model

Files:

- Modify: `app/rss.py`
- Modify: `app/main.py`
- Tests: `tests/test_rss.py`, `tests/test_api_flows.py`

Tasks:

1. Add safe SQLite migration helper for missing feed columns.
2. Add `color`, `collapsed`, `show_in_combined`, `display_limit`, refresh status fields.
3. Extend `FeedCreateRequest` and `FeedPatchRequest`.
4. Validate color and display limit.
5. Extend `_public_feed()` to expose safe fields only.
6. Extend `list_items()` to join feed metadata and respect combined/list filtering.
7. Add tests for old DB migration, patching feed preferences, redaction, and combined visibility.

Validation commands:

```bash
uv run --python /home/hermes/.local/bin/python3.11 --with-requirements requirements.txt --with pytest python -m pytest tests/test_rss.py tests/test_api_flows.py -q
```

Manual checks:

```bash
curl -fsS http://127.0.0.1:8008/api/feeds | jq '.items[0]'
curl -fsS -X PATCH http://127.0.0.1:8008/api/feeds/1 \
  -H 'Content-Type: application/json' \
  -d '{"color":"#fff7e6","display_limit":15,"show_in_combined":true,"collapsed":false}' | jq
curl -fsS 'http://127.0.0.1:8008/api/rss/items?combined=true' | jq '.items[0]'
```

### Phase 3: History ABS Metadata and Resolver

Files:

- Modify: `app/history_store.py`
- Modify: `app/main.py`
- Possibly create: `app/abs_client.py`
- Tests: `tests/test_history_store.py` or `tests/test_api_flows.py`

Tasks:

1. Add History migration fields for ABS metadata.
2. Add settings for `ABS_TOKEN` and optional `ABS_LIBRARY_ID`.
3. Create `AbsClient` with no side effects: search/list only.
4. Add resolver endpoint `POST /api/history/{row_id}/resolve-abs`.
5. Add response fields to `/api/history`.
6. Add tests using mocked ABS client responses:
   - no config
   - one match
   - no match
   - ambiguous matches
   - ABS HTTP error

Validation commands:

```bash
uv run --python /home/hermes/.local/bin/python3.11 --with-requirements requirements.txt --with pytest python -m pytest tests/test_api_flows.py -q
```

Manual checks require real ABS config and should not print token:

```bash
curl -fsS http://127.0.0.1:8008/api/status | jq '.abs'
curl -fsS -X POST http://127.0.0.1:8008/api/history/1/resolve-abs | jq
curl -fsS http://127.0.0.1:8008/api/history | jq '.items[0] | {title,abs_match_status,abs_item_url}'
```

### Phase 4: Excel-Style Table Helper

Files:

- Modify or create: `app/static/table.js`
- Modify: `app/static/app.js`
- Modify: `app/templates/index.html`
- Tests: no browser test framework currently; use `node --check`, browser smoke, and optional lightweight JS unit tests if introduced.

Tasks:

1. Build a reusable `createDataTable()` helper for sorting/filtering/rendering.
2. Replace current search table manual rendering with column definitions.
3. Add dynamic checkbox filter menus.
4. Add header click sorting with visible sort indicators.
5. Ensure Add/MAM link columns remain action columns, not sortable/filterable unless explicitly useful.
6. Apply table helper to RSS combined list where practical.

Validation commands:

```bash
node --check app/static/app.js
[ -f app/static/table.js ] && node --check app/static/table.js || true
```

Browser checks:

- Load `/`.
- Search blank.
- Verify default preset status text.
- Click `Seeders` header: numeric sorting changes row order.
- Click `Uploaded` header: date sorting changes row order.
- Open `Author` filter menu; values are generated from current results.
- Select one author; rows filter to that author.
- Select multiple values in one column; OR behavior works.
- Apply author + narrator filters; AND behavior works.
- Clear filters; full result count returns.
- No JS errors.

### Phase 5: RSS Dashboard UI

Files:

- Modify: `app/templates/index.html`
- Modify: `app/static/app.js`
- Possibly modify: `app/static/table.js`

Tasks:

1. Redesign feed config table with editable controls.
2. Add color picker/text color input with validation feedback.
3. Add enabled/show/collapsed toggles.
4. Add display limit control defaulting to 15.
5. Add inline edit Save/Cancel behavior for name/kind/url/color/toggles.
6. Add delete with confirmation.
7. Render combined RSS items with feed color background.
8. Honor `show_in_combined`, `display_limit`, hidden/grabbed toggles.

Browser checks:

- Rename feed and refresh: new name persists after reload.
- Change color: combined RSS rows lightly change color.
- Toggle `Show in combined` off: feed's items disappear from combined list.
- Toggle back on: items return.
- Set display limit to 3: only 3 visible items for that feed in combined mode.
- Collapse feed: per-feed group hides without deleting feed.
- URL remains redacted; no secret URL appears in DOM snapshot/API response.

### Phase 6: History ABS Link UI

Files:

- Modify: `app/templates/index.html`
- Modify: `app/static/app.js`

Tasks:

1. Split History `Link` column into `MAM` and `ABS` columns.
2. Render ABS status states.
3. Add optional `Resolve ABS` action for rows lacking a matched ABS URL.
4. Ensure History still loads if ABS config is absent.

Browser checks:

- History loads.
- MAM link still opens torrent page.
- ABS matched rows show clickable link.
- ABS missing/unconfigured rows show muted status, not broken links.

---

## 7. Test and Validation Matrix

### 7.1 Unit/Contract Tests

Required tests:

- `tests/test_presets.py`
  - blank default preset uses `m4b`, bookmark fields, 3-month date, selected sort.
  - targeted preset uses user query, focused fields, selected sort.
  - invalid sort falls back safely.
  - perpage/page clamped.
- `tests/test_rss.py`
  - feed migration adds new columns to old DB.
  - patch validates color.
  - patch clamps display limit.
  - public feed response redacts `url_secret`.
  - list items includes feed name/color/show metadata.
  - combined listing respects `show_in_combined`.
- `tests/test_api_flows.py`
  - `/api/search?q=` routes to default preset.
  - `/api/search?q=bobiverse` routes to targeted preset.
  - `/api/feeds/{id}` patches QoL fields.
  - `/api/rss/items` supports combined/limit parameters.
  - `/api/history` includes ABS fields.
- `tests/test_history_store.py` if created
  - migration adds ABS columns.
  - marking grabbed preserves existing ABS fields.
  - resolving ABS updates only ABS fields.

### 7.2 Frontend Static Checks

Required:

```bash
node --check app/static/app.js
[ -f app/static/table.js ] && node --check app/static/table.js || true
```

### 7.3 Full Regression

Required before rebuild:

```bash
uv run --python /home/hermes/.local/bin/python3.11 --with-requirements requirements.txt --with pytest python -m pytest -q
```

Expected:

```text
all tests pass
```

### 7.4 Container Validation

Required after code changes:

```bash
sg docker -c 'docker build -t seanap/maf:latest .'
sg docker -c 'docker rm -f maf-review >/dev/null 2>&1 || true; docker run -d --name maf-review -p 8008:8080 --env-file /home/hermes/projects/MAF/.env -e DATA_DIR=/data -v /home/hermes/.cache/maf-review-data:/data seanap/maf:latest'
curl -fsS http://127.0.0.1:8008/health
```

### 7.5 Live Smoke Tests

Required, with secrets redacted:

```bash
curl -fsS 'http://127.0.0.1:8008/api/search?q=&perpage=25' | jq '.preset,.window,.query_text,.items|length'
curl -fsS 'http://127.0.0.1:8008/api/search?q=bobiverse&sort=seedersDesc&perpage=25' | jq '.sort,.items[0:3][] | {title,seeders,format}'
curl -fsS http://127.0.0.1:8008/api/feeds | jq '.items[] | {id,name,color,collapsed,show_in_combined,display_limit,url_redacted}'
curl -fsS http://127.0.0.1:8008/api/history | jq '.items[0] | {title,torrent_id,abs_match_status,abs_item_url}'
```

### 7.6 Browser Validation

Use browser tools or manual browser:

- Blank search displays recent advanced search results and says it used default 3-month M4B preset.
- Header sort works for text, number, date.
- Filter menu checkbox behavior works.
- Feed edit/save persists after reload.
- Feed color affects combined RSS list softly.
- Feed visibility/display limit/collapse work.
- History shows MAM and ABS columns.
- No JS errors.

---

## 8. Adversarial Review

### 8.1 User Alignment

Finding: Sean wants a remote request surface, not a general library manager.

Resolution in spec:

- qBit remains the only download target.
- ABS is link-only/metadata visibility, not a file mover.
- Calibre remains out of scope.

### 8.2 Blank Search Ambiguity

Finding: Prior fix made blank/default search all-time, which conflicts with Sean's explicit request for the 3-month advanced bookmark behavior.

Resolution in spec:

- Blank search explicitly maps to `default_advanced_3mo`.
- UI must disclose that preset is being used.
- Non-blank search can still remain targeted and less noisy.

### 8.3 Sorting Failure Risk

Finding: There are two different sorts: MAM backend sort and client-side table sort. Mixing them can confuse users.

Resolution in spec:

- Backend response must echo sort metadata.
- Header sorting becomes the primary Excel-like table sort.
- Existing sort dropdown should either be removed or labeled `MAM sort`.

### 8.4 RSS Secret Exposure Risk

Finding: Feed edit could accidentally reveal private RSS tokens if the full URL is placed back into the browser.

Resolution in spec:

- Public feed DTO never includes `url_secret`.
- Edit URL field remains blank unless changing URL.
- Redacted URL display only.

### 8.5 ABS Link Timing Risk

Finding: ABS scans asynchronously. MAF cannot assume the book exists in ABS immediately after qBit add.

Resolution in spec:

- ABS resolution is optional and non-blocking.
- History supports pending/not_found/ambiguous/matched states.
- Add-to-qBit flow is not delayed by ABS resolution.

### 8.6 ABS API Guessing Risk

Finding: Direct ABS item URL shape and API query details must match installed ABS version. Guessing could produce broken links.

Resolution in spec:

- Implementation must verify direct ABS URL format against deployed ABS.
- If uncertain, use a safe ABS search fallback or keep muted status.
- Tests mock behavior; live validation confirms real URL.

### 8.7 UI Scope Creep Risk

Finding: Full Excel parity can balloon into a frontend rewrite.

Resolution in spec:

- Limit to sorting + dynamic checkbox filters + clear/select all.
- No framework.
- No pivot aggregation/grouping beyond requested filtering/sorting.

### 8.8 Performance Risk

Finding: Dynamic filters over hundreds of rows are fine; thousands may lag in vanilla DOM rendering.

Resolution in spec:

- Keep server result limits clamped.
- RSS defaults to 15 per feed.
- No infinite scrolling in this iteration.

### 8.9 Test Coverage Risk

Finding: Frontend behavior lacks formal browser automation tests.

Resolution in spec:

- Backend/data contract tests are mandatory.
- JS syntax checks are mandatory.
- Browser smoke checklist is mandatory.
- If frontend complexity grows further, add Playwright in a future spec, not silently now.

---

## 9. Definition of Done

This work is complete when:

- Blank search uses Sean's 3-month advanced MAM bookmark behavior.
- Header sorting works for search table columns.
- Dynamic checkbox filter menus work from loaded result values.
- RSS feeds can be renamed, edited, colored, enabled/disabled, collapsed, hidden from combined list, and display-limited.
- Combined RSS list defaults to 15 visible items per feed and uses subtle feed row coloring.
- History displays separate MAM and ABS link/status columns.
- Secrets are not leaked in API responses, DOM, logs, or localStorage.
- Full test suite passes.
- Container is rebuilt and live smoke tests pass.
- Changes are committed and pushed.

---

## 10. Implementation Order Recommendation

1. Backend search preset contract.
2. Backend feed/history schema and API extensions.
3. Table helper and search table UI.
4. RSS dashboard UI.
5. ABS resolver and History UI.
6. End-to-end verification and commit.

This order keeps the monkey habitat stable: backend contracts first, UI second, ABS optional integration last.
