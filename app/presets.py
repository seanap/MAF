from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

AUDIOBOOK_CATEGORY_IDS = [39, 50, 83, 51, 97, 40, 41, 106, 42, 52, 98, 54, 55, 43, 99, 84, 56, 45, 57, 85, 87, 119, 88, 59, 47, 53, 89, 100, 0]
SEARCH_FIELDS = ["title", "author", "narrator", "series"]
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


def build_m4b_search_payload(
    *,
    q: str = "",
    window: str = "past_4_months",
    page: int = 0,
    perpage: int = 25,
    sort: str = "snatchedDesc",
    today: date | None = None,
) -> dict:
    q = " ".join((q or "").strip().split())[:160]
    text = q
    page = max(0, int(page or 0))
    perpage = min(100, max(1, int(perpage or 25)))
    sort = sort if sort in SORT_TYPES else "snatchedDesc"
    start_date = compute_start_date(window, today=today)
    tor = {
        "text": text,
        "searchType": "all",
        "searchIn": "torrents",
        "srchIn": SEARCH_FIELDS[:],
        "sortType": sort,
        "startNumber": str(page * perpage),
        "main_cat": AUDIOBOOK_CATEGORY_IDS[:],
        "browse_lang": [1],
        "browseFlagsHideVsShow": 0,
        "browseFlags": [32],
        "unit": 1,
    }
    if start_date:
        tor["startDate"] = start_date
    return {
        "tor": tor,
        "perpage": perpage,
    }


def presets_metadata() -> dict:
    return {
        "default": "recent_m4b_snatched",
        "windows": ["all", "past_3_months", "past_4_months", "past_12_months", "YYYY-MM-DD"],
        "categories": AUDIOBOOK_CATEGORY_IDS,
        "fields": SEARCH_FIELDS,
        "sorts": sorted(SORT_TYPES),
    }
