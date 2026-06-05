# Adversarial Review — Next-Step Specs

Status: incorporated into implementation requirements.

## Step 1/2 Required Corrections

- Adapters and add flow must not depend on `LIB_DIR`, `DL_DIR`, `QB_PATH_MAP`, Calibre, ABS import, or file-moving workflows.
- MAM torrent ids must be numeric-only after trimming. Reject blank, URL-like, path-like, query-containing, encoded-delimiter, and non-numeric ids before any outbound call.
- MAM download URLs are backend-generated only: `/tor/download.php?tid=<id>` plus `fl=1` only when wedge decision says yes.
- MAM client must reject cross-host redirects, HTML/login pages, empty torrent bodies, and oversized torrent responses.
- Adapter exceptions and API errors must redact cookies, passwords, private URLs, headers, and long upstream bodies.
- qBit auth must support `Ok.` and local auth bypass, and failures must be explicit.
- qBit add must validate `200 Ok.`/duplicate-ish responses, not only status code.
- qBit multipart upload field is `torrents`; generated filename is `mam-<id>.torrent`; empty save path means omit `savepath`.
- Legacy `/add` must not accept/forward browser-provided private `dl` URLs. It may accept numeric id only.
- Failed MAM fetch must not call qBit. Failed qBit upload must not mark grabbed.

## Step 3/4 Required Corrections

- `canonical_key` is exactly `mam:torrent:<torrent_id>` for MAM torrent rows.
- Work-level suppression is out of scope; do not overload title/author matching.
- Use a current-state table or transactional upsert for idempotent grabbed/hidden state. Duplicate clicks must not create duplicate grabbed rows.
- Hide/unhide must not delete grabbed audit state.
- qBit duplicate after a successful MAM fetch counts as grabbed once.
- Wedge policy defaults: `WEDGE_MODE=smart`, `WEDGE_UNKNOWN_FALLBACK=true`.
- Wedge decision is a pure function over normalized metadata and config.
- Unknown metadata means missing reliable freeleech indicators, not explicit `false` values.
- Add request override semantics: `null` means configured policy; explicit `true/false` may force behavior and must be recorded.

## Step 5/6 Required Corrections

- Advanced M4B category ids are explicit: `39, 50, 83, 51, 97, 40, 41, 106, 42, 52, 98, 54, 55, 43, 99, 84, 56, 45, 57, 85, 87, 119, 88, 59, 47, 53, 89, 100, 0`.
- Search `window` values: `past_3_months`, `past_4_months`, `past_12_months`, or explicit `YYYY-MM-DD`; unsupported values return 400.
- Search input is trimmed, length-limited, and appended as plain text. Browser cannot submit arbitrary MAM POST payloads through the new API.
- M4B search is a strong bias, not a perfect guarantee; normalization flags uncertain results.
- RSS is MAM-only by default. Reject non-MAM feed URLs.
- RSS URLs are secrets: redacted in API responses, logs, errors, and raw item storage.
- Feed refresh must be size/time/item-count limited, parser-safe, and transactional: a bad refresh does not wipe previous items.
- Add from RSS passes only torrent id/canonical key to `/api/torrents/add`; never feed URL or private download URL.
- Step 6 is manual refresh only; scheduled polling is out of scope for this implementation batch.

## Final rejection conditions

Reject if any implementation:

- moves/copies/hardlinks/renames audiobook files;
- sends qBit a private MAM URL instead of torrent bytes;
- leaks private MAM/RSS/qBit/ABS secrets in API responses or logs;
- allows arbitrary outbound fetch URLs from request bodies;
- overrides qBit save path when `QB_SAVEPATH` is blank;
- requires live MAM/qBit/ABS during unit tests or app startup.
