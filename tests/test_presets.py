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
    payload = build_m4b_search_payload(q=" dune ", window="past_4_months", page=2, perpage=25, today=date(2026, 6, 5))
    tor = payload["tor"]

    assert tor["text"] == "m4b dune"
    assert tor["searchType"] == "all"
    assert tor["sortType"] == "snatchedDesc"
    assert tor["startNumber"] == "50"
    assert payload["perpage"] == 25
    assert "fileTypes" in tor["srchIn"]
    assert "browse_lang" in tor
    assert 39 in tor["main_cat"]
