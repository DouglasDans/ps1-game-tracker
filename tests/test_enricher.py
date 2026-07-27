from unittest.mock import MagicMock, patch

import pytest

from daemon.db import get_unenriched_games, increment_enrichment_retries, upsert_game
import requests as _requests

from daemon.enricher import RateLimitError, _igdb_search, enrich_game

IGDB_CONFIG = {"igdb": {"client_id": "test_client", "client_secret": "test_secret"}}

IGDB_RESPONSE = [
    {
        "id": 375,
        "name": "Metal Gear Solid",
        "cover": {"id": 545996, "image_id": "cobpak"},
        "genres": [{"id": 5, "name": "Shooter"}, {"id": 24, "name": "Tactical"}],
        "first_release_date": 904780800,
        "summary": "A stealth game about Solid Snake infiltrating Shadow Moses Island.",
        "involved_companies": [
            {"company": {"name": "Konami"}, "developer": True, "publisher": False},
            {"company": {"name": "Konami Digital Entertainment"}, "developer": False, "publisher": True},
        ],
        "game_modes": [{"name": "Single player"}],
    }
]


def _row(conn, file_path: str) -> dict:
    return dict(
        conn.execute(
            "SELECT id, file_path, display_name, platform, canonical_name, "
            "enriched_at, enrichment_retries, cover_url, igdb_id, release_year, genre, "
            "summary, developer, publisher, game_modes "
            "FROM games WHERE file_path = ?",
            (file_path,),
        ).fetchone()
    )


def test_enrich_game_igdb_success(conn):
    upsert_game(conn, "/roms/PS1/Metal Gear Solid.chd", "Metal Gear Solid", "PS1", "Metal Gear Solid")
    game = _row(conn, "/roms/PS1/Metal Gear Solid.chd")

    with patch("daemon.enricher._get_igdb_token", return_value="tok"), \
         patch("daemon.enricher._igdb_search", return_value={
             "display_name": "Metal Gear Solid",
             "cover_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/cobpak.jpg",
             "genre": "Shooter, Tactical",
             "release_year": 1998,
             "igdb_id": 375,
             "summary": "A stealth game about Solid Snake infiltrating Shadow Moses Island.",
             "developer": "Konami",
             "publisher": "Konami Digital Entertainment",
             "game_modes": "Single player",
         }):
        result = enrich_game(conn, game, IGDB_CONFIG)

    assert result is True
    row = _row(conn, "/roms/PS1/Metal Gear Solid.chd")
    assert row["enriched_at"] is not None
    assert row["enrichment_retries"] == 0
    assert row["igdb_id"] == 375
    assert row["cover_url"] is not None
    assert row["release_year"] == 1998
    assert row["genre"] == "Shooter, Tactical"
    assert row["summary"] == "A stealth game about Solid Snake infiltrating Shadow Moses Island."
    assert row["developer"] == "Konami"
    assert row["publisher"] == "Konami Digital Entertainment"
    assert row["game_modes"] == "Single player"


def test_enrich_game_igdb_not_found_increments_retries(conn):
    upsert_game(conn, "/roms/PS1/Unknown.chd", "Unknown", "PS1", "Unknown")
    game = _row(conn, "/roms/PS1/Unknown.chd")

    with patch("daemon.enricher._get_igdb_token", return_value="tok"), \
         patch("daemon.enricher._igdb_search", return_value=None):
        result = enrich_game(conn, game, IGDB_CONFIG)

    assert result is False
    row = _row(conn, "/roms/PS1/Unknown.chd")
    assert row["enriched_at"] is None
    assert row["enrichment_retries"] == 1


def test_enrich_game_igdb_exception_increments_retries(conn):
    upsert_game(conn, "/roms/PS1/Crash.chd", "Crash", "PS1", "Crash")
    game = _row(conn, "/roms/PS1/Crash.chd")

    with patch("daemon.enricher._get_igdb_token", return_value="tok"), \
         patch("daemon.enricher._igdb_search", side_effect=Exception("timeout")):
        result = enrich_game(conn, game, IGDB_CONFIG)

    assert result is False
    row = _row(conn, "/roms/PS1/Crash.chd")
    assert row["enriched_at"] is None
    assert row["enrichment_retries"] == 1


def test_enrich_game_no_igdb_config_marks_done(conn):
    upsert_game(conn, "/roms/PS1/Crash.chd", "Crash", "PS1", "Crash")
    game = _row(conn, "/roms/PS1/Crash.chd")

    result = enrich_game(conn, game, {})

    assert result is True
    row = _row(conn, "/roms/PS1/Crash.chd")
    assert row["enriched_at"] is not None


def test_enrich_game_empty_name_increments_retries(conn):
    upsert_game(conn, "/roms/PS1/x.chd")
    game = _row(conn, "/roms/PS1/x.chd")

    result = enrich_game(conn, game, IGDB_CONFIG)

    assert result is False
    row = _row(conn, "/roms/PS1/x.chd")
    assert row["enrichment_retries"] == 1


def test_igdb_search_includes_platform_filter():
    mock_resp = MagicMock()
    mock_resp.json.return_value = IGDB_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp) as mock_post:
        result = _igdb_search("Metal Gear Solid", "PS1", "tok", "cid")

    body = mock_post.call_args[1]["data"]
    assert "where platforms = (7)" in body
    assert result is not None
    assert result["igdb_id"] == 375
    assert result["display_name"] == "Metal Gear Solid"
    assert result["cover_url"] == "https://images.igdb.com/igdb/image/upload/t_cover_big/cobpak.jpg"
    assert result["genre"] == "Shooter, Tactical"
    assert result["release_year"] == 1998
    assert result["summary"] == "A stealth game about Solid Snake infiltrating Shadow Moses Island."
    assert result["developer"] == "Konami"
    assert result["publisher"] == "Konami Digital Entertainment"
    assert result["game_modes"] == "Single player"


def test_igdb_search_joins_multiple_developers():
    response = [{
        "id": 1,
        "name": "Co-Dev Game",
        "involved_companies": [
            {"company": {"name": "Studio A"}, "developer": True, "publisher": False},
            {"company": {"name": "Studio B"}, "developer": True, "publisher": False},
            {"company": {"name": "Publisher Only"}, "developer": False, "publisher": True},
        ],
    }]
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp):
        result = _igdb_search("Co-Dev Game", "PS1", "tok", "cid")

    assert result["developer"] == "Studio A, Studio B"
    assert result["publisher"] == "Publisher Only"


def test_igdb_search_developer_and_publisher_can_be_the_same_company():
    # Self-published title: one company flagged as both developer and publisher.
    response = [{
        "id": 2,
        "name": "Self Published Game",
        "involved_companies": [
            {"company": {"name": "Indie Co"}, "developer": True, "publisher": True},
        ],
    }]
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp):
        result = _igdb_search("Self Published Game", "PS1", "tok", "cid")

    assert result["developer"] == "Indie Co"
    assert result["publisher"] == "Indie Co"


def test_igdb_search_publisher_none_when_no_publisher_credited():
    # Indie/homebrew title with no publisher entry at all.
    response = [{
        "id": 3,
        "name": "Homebrew Game",
        "involved_companies": [
            {"company": {"name": "Solo Dev"}, "developer": True, "publisher": False},
        ],
    }]
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp):
        result = _igdb_search("Homebrew Game", "PS1", "tok", "cid")

    assert result["publisher"] is None


def test_igdb_search_omits_platform_filter_for_unknown_platform():
    mock_resp = MagicMock()
    mock_resp.json.return_value = IGDB_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp) as mock_post:
        _igdb_search("Metal Gear Solid", "Atari 2600", "tok", "cid")

    body = mock_post.call_args[1]["data"]
    assert "where" not in body


def test_igdb_search_returns_none_when_empty():
    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp):
        result = _igdb_search("Does Not Exist", "PS1", "tok", "cid")

    assert result is None


def test_enrich_game_429_raises_rate_limit_error_without_incrementing_retries(conn):
    upsert_game(conn, "/roms/PS1/Crash.chd", "Crash", "PS1", "Crash")
    game = _row(conn, "/roms/PS1/Crash.chd")

    mock_response = MagicMock()
    mock_response.status_code = 429
    http_error = _requests.HTTPError(response=mock_response)

    with patch("daemon.enricher._get_igdb_token", return_value="tok"), \
         patch("daemon.enricher._igdb_search", side_effect=http_error):
        with pytest.raises(RateLimitError):
            enrich_game(conn, game, IGDB_CONFIG)

    row = _row(conn, "/roms/PS1/Crash.chd")
    assert row["enrichment_retries"] == 0


def test_igdb_search_handles_missing_cover():
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"id": 1, "name": "No Cover Game"}]
    mock_resp.raise_for_status = MagicMock()

    with patch("daemon.enricher.requests.post", return_value=mock_resp):
        result = _igdb_search("No Cover Game", "PS1", "tok", "cid")

    assert result is not None
    assert result["cover_url"] is None
    assert result["genre"] is None
    assert result["release_year"] is None
    assert result["summary"] is None
    assert result["developer"] is None
    assert result["publisher"] is None
    assert result["game_modes"] is None
