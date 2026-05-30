import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from daemon.db import upsert_game
from daemon.session_manager import normalize_game_name

logger = logging.getLogger(__name__)

_PLATFORM_MAP = {
    # Sony
    "Sony - PlayStation": "PS1",
    "Sony - PlayStation 2": "PS2",
    "Sony - PlayStation 3": "PS3",
    "Sony - PlayStation 4": "PS4",
    "Sony - PlayStation 5": "PS5",
    "Sony - PlayStation Portable": "PSP",
    "Sony - PlayStation Vita": "PS Vita",
    # Nintendo
    "Nintendo - Nintendo Entertainment System": "NES",
    "Nintendo - Super Nintendo Entertainment System": "SNES",
    "Nintendo - Nintendo 64": "N64",
    "Nintendo - GameCube": "GameCube",
    "Nintendo - Wii": "Wii",
    "Nintendo - Wii U": "Wii U",
    "Nintendo - Nintendo Switch": "Switch",
    "Nintendo - Game Boy": "Game Boy",
    "Nintendo - Game Boy Color": "GBC",
    "Nintendo - Game Boy Advance": "GBA",
    "Nintendo - Nintendo DS": "DS",
    "Nintendo - Nintendo DSi": "DSi",
    "Nintendo - Nintendo 3DS": "3DS",
    "Nintendo - New Nintendo 3DS": "New 3DS",
    "Nintendo - Virtual Boy": "Virtual Boy",
    # Sega
    "Sega - Mega Drive - Genesis": "Mega Drive",
    "Sega - Master System - Mark III": "Master System",
    "Sega - Saturn": "Saturn",
    "Sega - Dreamcast": "Dreamcast",
    "Sega - Game Gear": "Game Gear",
    "Sega - 32X": "32X",
    "Sega - CD": "Sega CD",
    # Others
    "Microsoft - MSX": "MSX",
    "Microsoft - MSX2": "MSX2",
    "Microsoft - Xbox": "Xbox",
    "Microsoft - Xbox 360": "Xbox 360",
    "Microsoft - Xbox One": "Xbox One",
    "NEC - PC Engine - TurboGrafx 16": "PC Engine",
    "NEC - PC Engine SuperGrafx": "PC Engine SuperGrafx",
    "SNK - Neo-Geo Pocket": "Neo-Geo Pocket",
    "SNK - Neo-Geo Pocket Color": "Neo-Geo Pocket Color",
    "Bandai - WonderSwan": "WonderSwan",
    "Bandai - WonderSwan Color": "WonderSwan Color",
}


def _platform_from_db_name(db_name: str) -> str | None:
    if not db_name:
        return None
    stem = db_name.removesuffix(".lpl")
    if stem in _PLATFORM_MAP:
        return _PLATFORM_MAP[stem]
    # fallback: "Brand - Console" → "Console"
    if " - " in stem:
        return stem.split(" - ", 1)[1]
    return stem


def _load_playlist_map(playlist_dirs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for d in playlist_dirs:
        for lpl_path in Path(d).expanduser().glob("*.lpl"):
            try:
                data = json.loads(lpl_path.read_text())
            except (OSError, json.JSONDecodeError):
                logger.warning("Failed to parse playlist %s", lpl_path)
                continue
            platform = _platform_from_db_name(lpl_path.name)
            for item in data.get("items", []):
                label = item.get("label") or Path(item.get("path", "")).stem
                if not label:
                    continue
                key = normalize_game_name(label).lower()
                if key:
                    result[key] = platform or ""
    return result


def _parse_lrtl(data: dict) -> tuple[int, datetime] | None:
    # Real format: {"version": "1.0", "runtime": "H:MM:SS", "last_played": "YYYY-MM-DD HH:MM:SS"}
    try:
        h, m, s = data["runtime"].split(":")
        runtime_s = int(h) * 3600 + int(m) * 60 + int(s)
        last_played = datetime.strptime(data["last_played"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError):
        return None
    if runtime_s <= 0:
        return None
    return runtime_s, last_played


def _known_runtime_s(conn: sqlite3.Connection, canonical_name: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(s.duration_s), 0)
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.source = 'retroarch'
          AND COALESCE(g.canonical_name, g.display_name) = ?
        """,
        (canonical_name,),
    ).fetchone()
    return row[0] if row else 0


def _insert_historical_session(
    conn: sqlite3.Connection,
    game_id: int,
    started_at: datetime,
    ended_at: datetime,
    duration_s: int,
) -> None:
    conn.execute(
        """
        INSERT INTO sessions (game_id, source, started_at, ended_at, heartbeat_at, duration_s)
        VALUES (?, 'retroarch', ?, ?, ?, ?)
        """,
        (
            game_id,
            started_at.strftime("%Y-%m-%d %H:%M:%S"),
            ended_at.strftime("%Y-%m-%d %H:%M:%S"),
            ended_at.strftime("%Y-%m-%d %H:%M:%S"),
            duration_s,
        ),
    )
    conn.commit()


def _import_file(conn: sqlite3.Connection, lrtl_path: Path, playlist_map: dict[str, str]) -> int:
    try:
        data = json.loads(lrtl_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to parse %s", lrtl_path)
        return 0

    parsed = _parse_lrtl(data)
    if not parsed:
        return 0

    content_name = normalize_game_name(lrtl_path.stem)
    runtime_s, last_played = parsed
    delta_s = runtime_s - _known_runtime_s(conn, content_name)
    if delta_s <= 0:
        return 0

    platform = playlist_map.get(content_name.lower()) or None
    file_path = f"retroarch://{content_name}"
    game_id = upsert_game(conn, file_path, display_name=content_name, canonical_name=content_name, platform=platform)
    started_at = last_played - timedelta(seconds=delta_s)
    _insert_historical_session(conn, game_id, started_at, last_played, delta_s)
    logger.info("Imported RetroArch session: %s (%ds)", content_name, delta_s)
    return 1


def migrate_retroarch_games(conn: sqlite3.Connection, playlist_dirs: list[str]) -> None:
    playlist_map = _load_playlist_map(playlist_dirs)

    rows = conn.execute(
        "SELECT id, file_path, COALESCE(canonical_name, display_name) AS name FROM games "
        "WHERE file_path LIKE 'retroarch://%'"
    ).fetchall()

    for row in rows:
        game_id = row["id"]
        old_name = row["name"]
        new_name = normalize_game_name(old_name)

        if new_name.lower() not in playlist_map:
            continue

        platform = playlist_map[new_name.lower()] or None
        new_file_path = f"retroarch://{new_name}"

        existing = conn.execute(
            "SELECT id FROM games WHERE file_path = ? AND id != ?", (new_file_path, game_id)
        ).fetchone()

        if existing:
            target_id = existing["id"]
            conn.execute("UPDATE sessions SET game_id = ? WHERE game_id = ?", (target_id, game_id))
            conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
            conn.execute("UPDATE games SET platform = COALESCE(platform, ?) WHERE id = ?", (platform, target_id))
            conn.commit()
            logger.info("Merged '%s' into existing game id=%d", old_name, target_id)
        else:
            conn.execute(
                "UPDATE games SET file_path = ?, display_name = ?, canonical_name = ?, platform = ? WHERE id = ?",
                (new_file_path, new_name, new_name, platform, game_id),
            )
            conn.commit()
            logger.info("Migrated RetroArch game: '%s' → '%s'", old_name, new_name)


def import_sessions(conn: sqlite3.Connection, playlist_dirs: list[str]) -> int:
    playlist_map = _load_playlist_map(playlist_dirs)
    imported = 0
    for playlist_dir in playlist_dirs:
        logs_dir = Path(playlist_dir).expanduser() / "logs"
        if not logs_dir.exists():
            continue
        for lrtl_path in logs_dir.rglob("*.lrtl"):
            imported += _import_file(conn, lrtl_path, playlist_map)
    return imported
