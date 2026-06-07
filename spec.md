# MAF Lightweight Performance Optimization Implementation Spec

> **For Hermes:** Execute task-by-task with validation after each phase. When a task is completed, comment it out in this file using an HTML comment so interrupted work can resume cleanly.

**Goal:** Make MAF feel minimal, fast, and mobile-first while preserving the dark archival blueprint identity and keeping covers/descriptions useful enough that the user does not need to jump back to MAM for basic browsing.

**Architecture:** Optimize perceived performance first: make hover paint cheap, reduce mobile compositing, lazy/throttle cover loading, and cache covers locally. Then reduce DOM/API payload weight with shared description UI, description previews, lazy dashboard initialization, and cheaper table rendering. Finally harden backend scale with indexes, capped RSS payloads, short search caching, and shared HTTP clients for MAM/CDN calls.

**Tech Stack:** FastAPI, SQLite, httpx, vanilla JavaScript, CSS, Docker, pytest/unittest, browser smoke tests.

**Status:** All 12 implementation tasks completed and commented out below. Validation pending/finalized in command log.

---

## Validation commands

Run before declaring done:

```bash
node --check app/static/app.js
uv run --python /home/hermes/.local/bin/python3.11 --with-requirements requirements.txt --with pytest python -m pytest -q
sg docker -c 'docker build -t seanap/maf:latest .'
sg docker -c 'docker rm -f maf-review >/dev/null 2>&1 || true; docker run -d --name maf-review -p 8008:8080 --env-file /home/hermes/projects/MAF/.env -e DATA_DIR=/data -v /home/hermes/.cache/maf-review-data:/data seanap/maf:latest'
```

Browser smoke after deploy:

- `http://127.0.0.1:8008/` loads.
- RSS rows render without blocking UI.
- Row hover highlight is instant enough to not feel laggy.
- Covers load progressively and are served from `/api/mam/cover/{id}`.
- Search still works and respects selected count.
- Filters still work, including zero-result recovery.
- Feed Settings opens and loads management rows.
- No JavaScript console errors.

---

## Phase 1 — Immediate perceived performance wins

<!-- COMPLETED Task 1: implemented and validated in this execution loop.
### Task 1: Simplify table hover paint

**Objective:** Make row hover instant by removing expensive transitions and row box-shadow.

**Files:**
- Modify: `app/templates/index.html`

**Implementation:**
- Remove table row transitions for `background`, `color`, and `box-shadow`.
- Replace row hover shadow with a cheap first-cell border/accent.
- Disable row hover styling on touch devices using `@media (hover: none)`.

**Acceptance criteria:**
- Row hover CSS no longer transitions `box-shadow`.
- Touch/mobile devices do not keep sticky hover effects.
- Browser smoke confirms row hover visually responds immediately.
-->

<!-- COMPLETED Task 2: implemented and validated in this execution loop.
### Task 2: Reduce decorative paint layers on mobile

**Objective:** Keep visual identity while preventing mobile GPUs from repainting multiple blended atmospheric layers.

**Files:**
- Modify: `app/templates/index.html`

**Implementation:**
- At `max-width: 680px`, hide or reduce expensive decorative layers: `body::before`, `body::after`, `.backdrop-filler`, `.backdrop-vignette`, `.backdrop-invert`, `.backdrop-noise`, and `.shell::before`.
- Keep a faint `.backdrop-grid` for blueprint identity.

**Acceptance criteria:**
- Mobile CSS disables expensive grain/noise/blend layers.
- Desktop identity remains intact.
-->

<!-- COMPLETED Task 3: implemented and validated in this execution loop.
### Task 3: Add async/lazy/throttled cover loading

**Objective:** Prevent cover image request stampedes and let row text become usable before covers finish.

**Files:**
- Modify: `app/static/app.js`

**Implementation:**
- `coverCell()` should create an image without assigning `src` immediately.
- Add `loading="lazy"`, `decoding="async"`, and `fetchPriority="low"`.
- Add an `IntersectionObserver` and small queue limiting concurrent cover image loads.
- Defer cover `src` assignment until the cover is near the viewport.

**Acceptance criteria:**
- Covers still appear.
- Initial table render does not synchronously assign all cover `src` values.
- JS syntax check passes.
-->

<!-- COMPLETED Task 4: implemented and validated in this execution loop.
### Task 4: Add server-side MAM cover disk cache

**Objective:** Make repeat cover loads local and fast instead of repeatedly proxying MAM CDN latency.

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api_flows.py` or new focused test file

**Implementation:**
- Cache successful covers under `DATA_DIR/covers/{torrent_id}.webp`.
- Cache misses under `DATA_DIR/covers/{torrent_id}.missing` for a short negative TTL.
- Serve cached covers with `FileResponse`.
- Fetch uncached covers through the shared MAM HTTP client and write atomically.
- Validate HTTP status and `image/*` content type.
- Return longer browser cache headers for successful covers.

**Acceptance criteria:**
- First cover request fetches upstream and writes cache.
- Second request serves from cache without upstream call.
- Negative cache prevents repeated failed upstream calls.
- Tests cover cache hit/miss behavior without leaking secrets.
-->

---

## Phase 2 — Keep the UI lightweight as it becomes more useful

<!-- COMPLETED Task 5: implemented and validated in this execution loop.
### Task 5: Replace per-row description tooltip DOM with one shared popover

**Objective:** Avoid hidden tooltip DOM per row and make descriptions better on mobile/touch.

**Files:**
- Modify: `app/static/app.js`
- Modify: `app/templates/index.html`

**Implementation:**
- Add one shared description popover/panel element.
- `coverCell()` should render a small description button only when a preview exists.
- Populate and open the shared popover on click/focus/hover intent.
- Add close handling for Escape, backdrop/click-away, and close button.

**Acceptance criteria:**
- No per-row `.desc-tooltip` nodes are created.
- Description preview can be opened from row affordance.
- Popover works with keyboard and mobile/touch.
-->

<!-- COMPLETED Task 6: implemented and validated in this execution loop.
### Task 6: Return description previews, not full descriptions, in list payloads

**Objective:** Keep RSS/search API payloads small while still providing useful hover/tap context.

**Files:**
- Modify: `app/mam.py`
- Modify: `app/rss.py`
- Modify: `app/static/app.js`
- Test: RSS/search normalization tests

**Implementation:**
- Normalize descriptions to `description_preview` capped at roughly 360 characters.
- Avoid exposing full `description` in list rows unless needed for compatibility tests; frontend should prefer `description_preview`.
- Strip HTML and collapse whitespace.

**Acceptance criteria:**
- Normalizers create `description_preview`.
- Preview is stripped/truncated.
- Frontend uses preview for description UI.
-->

<!-- COMPLETED Task 7: implemented and validated in this execution loop.
### Task 7: Lazy-load RSS dashboard after first paint

**Objective:** Make the initial page interactive before RSS/feed machinery starts.

**Files:**
- Modify: `app/static/app.js`

**Implementation:**
- Do not call `loadFeedsAndItems()` synchronously at script end.
- Load combined RSS after `requestIdleCallback` or a short timeout fallback.
- Keep page controls interactive immediately.

**Acceptance criteria:**
- RSS still loads automatically shortly after first paint.
- Initial JS startup does not synchronously fetch RSS/feed management before idle/timer.
-->

<!-- COMPLETED Task 8: implemented and validated in this execution loop.
### Task 8: Render Feed Settings only when expanded

**Objective:** Hidden settings should not cost startup render work.

**Files:**
- Modify: `app/static/app.js`

**Implementation:**
- Split feed management loading from combined RSS loading.
- Load combined RSS independently.
- Fetch/render feed settings rows only when `Feed Settings` is expanded, or after save/delete/refresh operations that require it.

**Acceptance criteria:**
- Combined RSS still shows.
- Collapsed Feed Settings does not render feed rows at startup.
- Expanding Feed Settings loads and renders feed controls.
-->

<!-- COMPLETED Task 9: implemented and validated in this execution loop.
### Task 9: Use DocumentFragment/replaceChildren for table rendering

**Objective:** Reduce DOM churn when filters/sorts rerender tables.

**Files:**
- Modify: `app/static/app.js`

**Implementation:**
- Replace direct row-by-row live `tbody.appendChild()` with a `DocumentFragment` and `replaceChildren()`.
- Preserve empty-row behavior and onRender callbacks.

**Acceptance criteria:**
- Sorting/filtering still works.
- Zero-result filter state still keeps headers visible.
- JS syntax check passes.
-->

---

## Phase 3 — Backend scale and repeated-use hardening

<!-- COMPLETED Task 10: implemented and validated in this execution loop.
### Task 10: Add SQLite indexes for RSS/history hot paths

**Objective:** Keep RSS/history queries fast as data grows.

**Files:**
- Modify: `app/rss.py`
- Modify: `app/history_store.py`
- Test: schema/index smoke tests if practical

**Implementation:**
- Add index for RSS feed/time ordering: `rss_items(feed_id, site_added_at DESC, rss_position ASC, id DESC)`.
- Add history/update ordering index for `item_state(updated_at DESC)`.

**Acceptance criteria:**
- Database initialization creates indexes idempotently.
- Existing tests pass.
-->

<!-- COMPLETED Task 11: implemented and validated in this execution loop.
### Task 11: Cap and limit RSS item payloads closer to backend

**Objective:** Prevent combined RSS responses from growing without bound.

**Files:**
- Modify: `app/main.py`
- Modify: `app/rss.py` if needed
- Test: `tests/test_rss.py` or API flow test

**Implementation:**
- Add a sane default combined RSS API cap, e.g. 200 rows after per-feed display limits.
- Preserve per-feed display limits.
- Allow explicit `limit` query parameter within safe bounds.

**Acceptance criteria:**
- Combined RSS endpoint does not return unbounded rows by default.
- Existing per-feed display-limit behavior remains correct.
-->

<!-- COMPLETED Task 12: implemented and validated in this execution loop.
### Task 12: Add short TTL search cache and shared HTTP client lifecycle

**Objective:** Reduce repeated upstream MAM latency and reuse outbound connections safely.

**Files:**
- Modify: `app/main.py`
- Modify: `app/mam.py` if needed
- Test: targeted API flow tests if practical

**Implementation:**
- Create FastAPI lifespan-managed shared `httpx.AsyncClient` for MAM/CDN calls.
- Use the shared client for MAM search, torrent download, and cover fetch where practical.
- Add short in-memory TTL cache for normalized MAM search pages keyed by query/window/page/perpage/sort.
- Keep local grabbed/hidden annotation fresh after cache retrieval.

**Acceptance criteria:**
- Repeated identical search within TTL avoids a repeated upstream MAM search call in tests or by inspection with mock client.
- App shuts down HTTP client cleanly.
- Search behavior and local state annotation remain correct.

---

## Completion log

Tasks below should be commented out as completed:

- [ ] Task 1: Simplify table hover paint
- [ ] Task 2: Reduce decorative paint layers on mobile
- [ ] Task 3: Add async/lazy/throttled cover loading
- [ ] Task 4: Add server-side MAM cover disk cache
- [ ] Task 5: Replace per-row description tooltip DOM with one shared popover
- [ ] Task 6: Return description previews, not full descriptions, in list payloads
- [ ] Task 7: Lazy-load RSS dashboard after first paint
- [ ] Task 8: Render Feed Settings only when expanded
- [ ] Task 9: Use DocumentFragment/replaceChildren for table rendering
- [ ] Task 10: Add SQLite indexes for RSS/history hot paths
- [ ] Task 11: Cap and limit RSS item payloads closer to backend
- [ ] Task 12: Add short TTL search cache and shared HTTP client lifecycle
-->


## Validation Notes

- Targeted validation passed: `node --check app/static/app.js` plus focused pytest suite for RSS/API/MAM client: `29 passed, 1 warning`.
- Full validation passed before Docker/browser deploy: `53 passed, 1 warning`.
- Docker image rebuilt as `seanap/maf:latest` and container `maf-review` restarted successfully.
- Browser smoke passed on `http://127.0.0.1:8008/`:
  - RSS rendered after idle with Feed Settings initially collapsed and zero feed-setting rows at startup.
  - Feed Settings expansion loaded 4 management rows on demand.
  - Shared description model verified by absence of per-row `.desc-tooltip` nodes.
  - Row transition computed as `none`.
  - Search `bobiverse` returned 10 rows and cover cells.
  - Zero-result filter state kept table/header visible and filter reopenable.
  - Console capture returned no JavaScript errors.
- Cover cache smoke passed: repeated `/api/mam/cover/1247511` requests served `200 image/webp` with `Cache-Control: public, max-age=2592000, immutable` in ~3.0ms then ~1.7ms.
