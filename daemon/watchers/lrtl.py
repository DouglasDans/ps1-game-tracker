import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from daemon.db import upsert_game

logger = logging.getLogger(__name__)


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


def _import_file(conn: sqlite3.Connection, lrtl_path: Path) -> int:
    try:
        data = json.loads(lrtl_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to parse %s", lrtl_path)
        return 0

    parsed = _parse_lrtl(data)
    if not parsed:
        return 0

    runtime_s, last_played = parsed
    content_name = lrtl_path.stem
    delta_s = runtime_s - _known_runtime_s(conn, content_name)
    if delta_s <= 0:
        return 0

    file_path = f"retroarch://{content_name}"
    game_id = upsert_game(conn, file_path, display_name=content_name, canonical_name=content_name)
    started_at = last_played - timedelta(seconds=delta_s)
    _insert_historical_session(conn, game_id, started_at, last_played, delta_s)
    logger.info("Imported RetroArch session: %s (%ds)", content_name, delta_s)
    return 1


def import_sessions(conn: sqlite3.Connection, playlist_dirs: list[str]) -> int:
    imported = 0
    for playlist_dir in playlist_dirs:
        logs_dir = Path(playlist_dir).expanduser() / "logs"
        if not logs_dir.exists():
            continue
        for lrtl_path in logs_dir.rglob("*.lrtl"):
            imported += _import_file(conn, lrtl_path)
    return imported
