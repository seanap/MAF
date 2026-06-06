from datetime import date

import pytest

from app.presets import build_m4b_search_payload, compute_start_date


def test_start_date_month_windows_cross_year():
    assert compute_start_date("past_4_months", today=date(2026, 1, 31)) == "2025-09-30"
    assert compute_start_date("past_12_months", today=date(2026, 2, 28)) == "2025-02-28"


def test_explicit_future_date_rejected():
    with pytest.raises(ValueError):
        compute_start_date("2999-01-01", today=date(2026, 6, 5))


def test_build_m4b_payload_is_backend_controlled():
    payload = build_m4b_search_payload(q=" dune ", window="all", page=2, perpage=25, today=date(2026, 6, 5), sort="seedersDesc")
    tor = payload["tor"]

    assert tor["text"] == "dune"
    assert tor["searchType"] == "all"
    assert tor["sortType"] == "seedersDesc"
    assert tor["startNumber"] == "50"
    assert payload["perpage"] == 25
    assert "description" not in tor["srchIn"]
    assert "filenames" not in tor["srchIn"]
    assert "startDate" not in tor
    assert "browse_lang" in tor
    assert 39 in tor["main_cat"]


def test_build_m4b_payload_preserves_explicit_date_window():
    payload = build_m4b_search_payload(q="bobiverse", window="past_12_months", today=date(2026, 6, 5))

    assert payload["tor"]["startDate"] == "2025-06-05"


def test_build_m4b_payload_rejects_unknown_sort():
    payload = build_m4b_search_payload(q="dune", sort="bananaDesc")

    assert payload["tor"]["sortType"] == "snatchedDesc"
