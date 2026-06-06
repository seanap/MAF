from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

AUDIOBOOK_CATEGORY_IDS = [39, 50, 83, 51, 97, 40, 41, 106, 42, 52, 98, 54, 55, 43, 99, 84, 56, 45, 57, 85, 87, 119, 88, 59, 47, 53, 89, 100, 0]
TARGETED_SEARCH_FIELDS = ["title", "author", "narrator", "series"]
ADVANCED_SEARCH_FIELDS = ["title", "description", "tags", "author", "narrator", "series", "fileTypes", "filenames"]
WINDOW_MONTHS = {"past_3_months": 3, "past_4_months": 4, "past_12_months": 12}
SORT_TYPES = {"snatchedDesc", "seedersDesc", "dateDesc", "sizeDesc"}


def _subtract_months(value: date, months: int) -> date:
    month_index = value.month - 1 - months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def compute_start_date(window: str, *, today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    window = (window or "all").strip()
    if window in {"all", ""}:
        return ""
    if window in WINDOW_MONTHS:
        return _subtract_months(today, WINDOW_MONTHS[window]).isoformat()
    try:
        explicit = date.fromisoformat(window)
    except ValueError as exc:
        raise ValueError("Unsupported search date window") from exc
    if explicit > today:
        raise ValueError("Search start date cannot be in the future")
    return explicit.isoformat()


def _safe_sort(sort: str | None) -> str:
    return sort if sort in SORT_TYPES else "snatchedDesc"


def _safe_page(value: int | str | None) -> int:
    return max(0, int(value or 0))


def _safe_perpage(value: int | str | None) -> int:
    return min(100, max(1, int(value or 25)))


def _base_payload(*, text: str, fields: list[str], window: str, page: int, perpage: int, sort: str, today: date | None) -> dict:
    page = _safe_page(page)
    perpage = _safe_perpage(perpage)
    start_date = compute_start_date(window, today=today)
    tor = {
        "text": " ".join((text or "").strip().split())[:160],
        "searchType": "all",
        "searchIn": "torrents",
        "srchIn": fields[:],
        "sortType": _safe_sort(sort),
        "startNumber": str(page * perpage),
        "main_cat": AUDIOBOOK_CATEGORY_IDS[:],
        "browse_lang": [1],
        "browseFlagsHideVsShow": 0,
        "browseFlags": [32],
        "unit": 1,
    }
    if start_date:
        tor["startDate"] = start_date
    return {"tor": tor, "perpage": perpage}


def build_default_advanced_m4b_payload(*, window: str = "past_3_months", page: int = 0, perpage: int = 25, sort: str = "snatchedDesc", today: date | None = None) -> dict:
    return _base_payload(text="m4b", fields=ADVANCED_SEARCH_FIELDS, window=window or "past_3_months", page=page, perpage=perpage, sort=sort, today=today)


def build_targeted_m4b_search_payload(*, q: str, window: str = "all", page: int = 0, perpage: int = 25, sort: str = "snatchedDesc", today: date | None = None) -> dict:
    return _base_payload(text=q, fields=TARGETED_SEARCH_FIELDS, window=window, page=page, perpage=perpage, sort=sort, today=today)


def build_m4b_search_payload(*, q: str = "", window: str = "all", page: int = 0, perpage: int = 25, sort: str = "snatchedDesc", today: date | None = None) -> dict:
    """Backward-compatible targeted search builder."""
    return build_targeted_m4b_search_payload(q=q, window=window, page=page, perpage=perpage, sort=sort, today=today)


def build_search_payload_for_query(*, q: str = "", window: str = "", page: int = 0, perpage: int = 25, sort: str = "snatchedDesc", today: date | None = None) -> tuple[dict, dict]:
    q = " ".join((q or "").strip().split())
    if not q:
        effective_window = window or "past_3_months"
        payload = build_default_advanced_m4b_payload(window=effective_window, page=page, perpage=perpage, sort=sort, today=today)
        meta = {"preset": "default_advanced_3mo", "query_text": "m4b", "search_fields": ADVANCED_SEARCH_FIELDS[:], "window": effective_window}
    else:
        effective_window = window or "all"
        payload = build_targeted_m4b_search_payload(q=q, window=effective_window, page=page, perpage=perpage, sort=sort, today=today)
        meta = {"preset": "targeted_query", "query_text": q, "search_fields": TARGETED_SEARCH_FIELDS[:], "window": effective_window}
    meta["sort"] = payload["tor"].get("sortType", "snatchedDesc")
    return payload, meta


def presets_metadata() -> dict:
    return {
        "default": "default_advanced_3mo",
        "windows": ["all", "past_3_months", "past_4_months", "past_12_months", "YYYY-MM-DD"],
        "categories": AUDIOBOOK_CATEGORY_IDS,
        "targeted_fields": TARGETED_SEARCH_FIELDS,
        "advanced_fields": ADVANCED_SEARCH_FIELDS,
        "sorts": sorted(SORT_TYPES),
    }
