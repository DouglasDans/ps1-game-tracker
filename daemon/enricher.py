import json
import logging
import queue
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

from daemon.db import increment_enrichment_retries, update_game_enrichment

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    pass


_IGDB_PLATFORM_IDS: dict[str, int] = {
    # Sony
    "PS1": 7,
    "PS2": 8,
    "PS3": 9,
    "PS4": 48,
    "PS5": 167,
    "PSP": 38,
    "PS Vita": 46,
    # Nintendo
    "NES": 18,
    "SNES": 19,
    "N64": 4,
    "GameCube": 21,
    "Wii": 5,
    "Wii U": 41,
    "Switch": 130,
    "Game Boy": 33,
    "GBC": 22,
    "GBA": 24,
    "DS": 20,
    "DSi": 159,
    "3DS": 37,
    "New 3DS": 137,
    "Virtual Boy": 87,
    # Sega
    "Mega Drive": 29,
    "Master System": 64,
    "Saturn": 32,
    "Dreamcast": 23,
    "Game Gear": 35,
    "32X": 30,
    "Sega CD": 78,
    # Others
    "MSX": 27,
    "MSX2": 53,
    "Xbox": 11,
    "Xbox 360": 12,
    "Xbox One": 49,
    "PC Engine": 86,
    "PC Engine SuperGrafx": 128,
    "Neo-Geo Pocket": 119,
    "Neo-Geo Pocket Color": 120,
    "WonderSwan": 57,
    "WonderSwan Color": 123,
    # Atari — lrtl usa fallback "Brand - Console" → só o console
    "2600": 59,
    "5200": 66,
    "7800": 60,
    "Jaguar": 62,
    "Lynx": 61,
}


def _token_file(config: dict) -> Path:
    db_path = config.get("daemon", {}).get("db_path", "~/.local/share/ps1-tracker/tracker.db")
    return Path(db_path).expanduser().parent / "igdb_token.json"


def _get_igdb_token(config: dict) -> str | None:
    igdb_cfg = config.get("igdb")
    if not igdb_cfg:
        return None

    cache = _token_file(config)
    if cache.exists():
        try:
            cached = json.loads(cache.read_text())
            if cached.get("expires_at", 0) > time.time() + 3600:
                return cached["access_token"]
        except Exception:
            pass

    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": igdb_cfg["client_id"],
            "client_secret": igdb_cfg["client_secret"],
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({
        "access_token": data["access_token"],
        "expires_at": time.time() + data["expires_in"],
    }))
    return data["access_token"]


def _igdb_search(
    canonical_name: str,
    platform: str | None,
    token: str,
    client_id: str,
) -> dict | None:
    platform_id = _IGDB_PLATFORM_IDS.get(platform) if platform else None

    query = f'search "{canonical_name}"; fields name,genres.name,cover.image_id,first_release_date; '
    if platform_id:
        query += f"where platforms = ({platform_id}); "
    query += "limit 1;"

    resp = requests.post(
        "https://api.igdb.com/v4/games",
        headers={
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}",
        },
        data=query,
        timeout=10,
    )
    resp.raise_for_status()

    results = resp.json()
    if not results:
        return None

    game = results[0]
    cover_url = None
    if "cover" in game:
        cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{game['cover']['image_id']}.jpg"

    genre = None
    if "genres" in game:
        genre = ", ".join(g["name"] for g in game["genres"])

    release_year = None
    if "first_release_date" in game:
        release_year = datetime.fromtimestamp(game["first_release_date"]).year

    return {
        "display_name": game["name"],
        "cover_url": cover_url,
        "genre": genre,
        "release_year": release_year,
        "igdb_id": game["id"],
    }


def enrich_game(conn: sqlite3.Connection, game: dict, config: dict) -> bool:
    game_id = game["id"]
    canonical_name = game.get("canonical_name") or game.get("display_name") or ""
    platform = game.get("platform")

    igdb_cfg = config.get("igdb")
    if not igdb_cfg:
        update_game_enrichment(conn, game_id)
        return True

    if not canonical_name:
        increment_enrichment_retries(conn, game_id)
        return False

    try:
        token = _get_igdb_token(config)
        result = _igdb_search(canonical_name, platform, token, igdb_cfg["client_id"])
        if result:
            update_game_enrichment(conn, game_id, **result)
            logger.info("enriched '%s' → '%s' (igdb_id=%d)", canonical_name, result["display_name"], result["igdb_id"])
            return True
        else:
            logger.debug("igdb: no match for '%s' (platform=%s)", canonical_name, platform)
            increment_enrichment_retries(conn, game_id)
            return False
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise RateLimitError() from e
        logger.exception("enrichment http error for game_id=%d ('%s')", game_id, canonical_name)
        increment_enrichment_retries(conn, game_id)
        return False
    except Exception:
        logger.exception("enrichment error for game_id=%d ('%s')", game_id, canonical_name)
        increment_enrichment_retries(conn, game_id)
        return False


def enricher_loop(
    conn: sqlite3.Connection,
    config: dict,
    stop: threading.Event,
    q: queue.Queue,
) -> None:
    while not stop.is_set():
        try:
            game = q.get(timeout=1)
        except queue.Empty:
            continue

        try:
            enrich_game(conn, game, config)
            stop.wait(0.3)  # stay under IGDB 4 req/s limit
        except RateLimitError:
            logger.warning("igdb rate limit, re-queuing '%s' (sleeping 10s)", game.get("canonical_name", "?"))
            q.put(game)
            stop.wait(10)
        except Exception:
            logger.exception("unexpected error enriching game_id=%d", game.get("id", 0))
        finally:
            q.task_done()
