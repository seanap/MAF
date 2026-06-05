import pytest


def test_qbit_add_omits_blank_savepath():
    from app.qbit import build_add_torrent_payload

    data, files = build_add_torrent_payload(
        torrent_bytes=b"d4:infodee",
        filename="mam-123.torrent",
        category="maf",
        tags=["MAM", "maf"],
        savepath="",
    )

    assert data == {"category": "maf", "tags": "MAM,maf"}
    assert "savepath" not in data
    assert files["torrents"][0] == "mam-123.torrent"


def test_qbit_response_validation_handles_fail_text():
    from app.qbit import validate_add_response, QbitError

    validate_add_response(200, "Ok.")
    assert validate_add_response(200, "Fails. Torrent already exists") == "duplicate"
    with pytest.raises(QbitError):
        validate_add_response(200, "Fails. bad path")
