from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

AUDIOBOOK_CATEGORY_IDS = [39, 50, 83, 51, 97, 40, 41, 106, 42, 52, 98, 54, 55, 43, 99, 84, 56, 45, 57, 85, 87, 119, 88, 59, 47, 53, 89, 100, 0]
SEARCH_FIELDS = ["title", "description", "tags", "author", "narrator", "series", "fileTypes", "filenames"]
WINDOW_MONTHS = {"past_3_months": 3, "past_4_months": 4, "past_12_months": 12}


def _subtract_months(value: date, months: int) -> date:
    month_index = value.month - 1 - months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def compute_start_date(window: str, *, today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    window = (window or "past_4_months").strip()
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
    today: date | None = None,
) -> dict:
    q = " ".join((q or "").strip().split())[:160]
    text = "m4b" if not q else f"m4b {q}"
    page = max(0, int(page or 0))
    perpage = min(100, max(1, int(perpage or 25)))
    start_date = compute_start_date(window, today=today)
    return {
        "tor": {
            "text": text,
            "searchType": "all",
            "searchIn": "torrents",
            "srchIn": SEARCH_FIELDS[:],
            "sortType": "snatchedDesc",
            "startNumber": str(page * perpage),
            "main_cat": AUDIOBOOK_CATEGORY_IDS[:],
            "browse_lang": [1],
            "browseFlagsHideVsShow": 0,
            "browseFlags": [32],
            "unit": 1,
            "startDate": start_date,
        },
        "perpage": perpage,
    }


def presets_metadata() -> dict:
    return {
        "default": "recent_m4b_snatched",
        "windows": ["past_3_months", "past_4_months", "past_12_months", "YYYY-MM-DD"],
        "categories": AUDIOBOOK_CATEGORY_IDS,
        "fields": SEARCH_FIELDS,
    }
