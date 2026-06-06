import pytest


def test_mam_download_url_rejects_unsafe_ids():
    from app.mam import MamClient, InvalidTorrentId

    client = MamClient("https://www.myanonamouse.net", "mam_id=secret")
    for bad in ["", "abc", "../1", "1&fl=1", "https://evil/1", "12?x=1", "12%26x=1"]:
        with pytest.raises(InvalidTorrentId):
            client.build_download_url(bad)


def test_mam_download_url_appends_wedge_only_when_requested():
    from app.mam import MamClient

    client = MamClient("https://www.myanonamouse.net/", "mam_id=secret")
    assert client.build_download_url("123") == "https://www.myanonamouse.net/tor/download.php?tid=123"
    assert client.build_download_url("123", use_wedge=True) == "https://www.myanonamouse.net/tor/download.php?tid=123&fl=1"


def test_normalize_mam_result_redacts_private_download_url():
    from app.mam import normalize_mam_result

    item = normalize_mam_result({
        "id": 123,
        "title": "T",
        "dl": "private-token",
        "isFree": "0",
        "author_info": '{"97743":"Dennis E Taylor"}',
        "narrator_info": '{"247":"Ray Porter"}',
        "series_info": '{"30522":["Bobiverse","1",1.0]}',
    })

    assert item["torrent_id"] == "123"
    assert item["canonical_key"] == "mam:torrent:123"
    assert item["author"] == "Dennis E Taylor"
    assert item["narrator"] == "Ray Porter"
    assert item["series"] == "Bobiverse"
    assert "dl" not in item
    assert "private-token" not in repr(item)


def test_torrent_content_validation_handles_string_content_type():
    from app.mam import MamError, validate_torrent_content

    assert validate_torrent_content(b"d4:infodee", "application/x-bittorrent") == b"d4:infodee"
    with pytest.raises(MamError):
        validate_torrent_content(b"<html>nope</html>", "text/html; charset=utf-8")
