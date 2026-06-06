from datetime import date

import pytest

from app.presets import (
    ADVANCED_SEARCH_FIELDS,
    TARGETED_SEARCH_FIELDS,
    build_default_advanced_m4b_payload,
    build_m4b_search_payload,
    build_search_payload_for_query,
    compute_start_date,
)


def test_start_date_month_windows_cross_year():
    assert compute_start_date("past_4_months", today=date(2026, 1, 31)) == "2025-09-30"
    assert compute_start_date("past_12_months", today=date(2026, 2, 28)) == "2025-02-28"
    assert compute_start_date("past_2_weeks", today=date(2026, 6, 5)) == "2026-05-22"
    assert compute_start_date("past_1_month", today=date(2026, 6, 5)) == "2026-05-05"
    assert compute_start_date("past_2_months", today=date(2026, 6, 5)) == "2026-04-05"
    assert compute_start_date("past_3_months", today=date(2026, 6, 5)) == "2026-03-05"


def test_explicit_future_date_rejected():
    with pytest.raises(ValueError):
        compute_start_date("2999-01-01", today=date(2026, 6, 5))


def test_targeted_m4b_payload_is_backend_controlled():
    payload = build_m4b_search_payload(q=" dune ", window="all", page=2, perpage=25, today=date(2026, 6, 5), sort="seedersDesc")
    tor = payload["tor"]

    assert tor["text"] == "dune"
    assert tor["searchType"] == "all"
    assert tor["sortType"] == "seedersDesc"
    assert tor["startNumber"] == "50"
    assert payload["perpage"] == 25
    assert tor["srchIn"] == TARGETED_SEARCH_FIELDS
    assert "description" not in tor["srchIn"]
    assert "filenames" not in tor["srchIn"]
    assert "startDate" not in tor
    assert "browse_lang" in tor
    assert 39 in tor["main_cat"]


def test_default_advanced_payload_matches_blank_search_bookmark_contract():
    payload = build_default_advanced_m4b_payload(window="past_3_months", today=date(2026, 6, 5), sort="dateDesc")
    tor = payload["tor"]

    assert tor["text"] == "m4b"
    assert tor["srchIn"] == ADVANCED_SEARCH_FIELDS
    assert tor["startDate"] == "2026-03-05"
    assert tor["sortType"] == "dateDesc"
    assert tor["browse_lang"] == [1]
    assert tor["browseFlagsHideVsShow"] == 0
    assert tor["browseFlags"] == [32]


def test_build_search_payload_for_query_blank_uses_default_advanced_3mo():
    payload, meta = build_search_payload_for_query(q="   ", today=date(2026, 6, 5))

    assert payload["tor"]["text"] == "m4b"
    assert payload["tor"]["srchIn"] == ADVANCED_SEARCH_FIELDS
    assert payload["tor"]["startDate"] == "2026-03-05"
    assert meta["preset"] == "default_advanced_3mo"
    assert meta["query_text"] == "m4b"
    assert meta["window"] == "past_3_months"


def test_build_search_payload_for_query_nonblank_uses_targeted_query():
    payload, meta = build_search_payload_for_query(q=" bobiverse ", window="all", today=date(2026, 6, 5))

    assert payload["tor"]["text"] == "bobiverse"
    assert payload["tor"]["srchIn"] == TARGETED_SEARCH_FIELDS
    assert "startDate" not in payload["tor"]
    assert meta["preset"] == "targeted_query"
    assert meta["query_text"] == "bobiverse"


def test_build_m4b_payload_preserves_explicit_date_window():
    payload = build_m4b_search_payload(q="bobiverse", window="past_12_months", today=date(2026, 6, 5))

    assert payload["tor"]["startDate"] == "2025-06-05"


def test_build_m4b_payload_rejects_unknown_sort():
    payload = build_m4b_search_payload(q="dune", sort="bananaDesc")

    assert payload["tor"]["sortType"] == "snatchedDesc"
