"""PS Vita play time -> sessions.

The vita-sync service on the Pi (repo vita-sync-pi) exports, after each save
cycle, one JSON per title: {"id", "seconds", "title", "mtime"}. `seconds` is
BetterTrackPlug's running total for that title; `mtime` is when the Vita last
wrote it (UTC ISO). This watcher turns the growth of the total into sessions.

Per ID we remember the last total seen (table vita_playtime_seen):
  - first reading: only the baseline, no session (the history before the
    integration is not reconstructed);
  - total grew: one session of the difference, ending at the file date;
  - total shrank (plugin data reset): new baseline, no session.
The session and the new baseline are written in one commit, so a crash never
counts the same seconds twice or loses them.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from daemon.db import upsert_game

logger = logging.getLogger(__name__)

SOURCE = "vita"

# Title IDs that are tools, launchers or system apps, not games. Their play
# time is never imported.
IGNORED_IDS = frozenset({
    "VITASHELL",   # VitaShell
    "EMU4VPLUS",   # Emu4Vita++ (one total for every emulator, no per-ROM time)
    "AUTOPLUG2",   # AutoPlugin II
    "TPLG00001",   # TrackPlug
    "VXMB00001",   # VitaXMB
    "VXMBUPDTR",   # VitaXMB Updater
    "UCJS10041",   # VitaXMB Launcher
    "VITADBDLD",   # VitaDB Downloader
    "SKGD3PL0Y",   # VitaDeploy
    "XYZZ00002",   # Moonlight
    "PCSI00011",   # untitled system bubble
})

_MARKS = re.compile(r"[®™©]")
_SPACES = re.compile(r"\s+")
_NOT_ALNUM = re.compile(r"[\W_]+")


def platform_for(game_id: str) -> str:
    """Adrenaline runs PS1 (SCUS/SLUS/SLES/SCES...) and PSP (ULUS/UCUS/ULES...)
    games as bubbles with their disc ID; everything else is a Vita title or
    homebrew."""
    prefix = game_id[:2]
    if prefix in ("SL", "SC"):
        return "PS1"
    if prefix in ("UL", "UC"):
        return "PSP"
    return "PS Vita"


def clean_title(title: str) -> str:
    return _SPACES.sub(" ", _MARKS.sub("", title)).strip()


def _key(name: str) -> str:
    return _NOT_ALNUM.sub("", name.lower())


def _ensure_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS vita_playtime_seen ("
        "game_id TEXT PRIMARY KEY, seconds INTEGER NOT NULL)"
    )


def _read_entry(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Vita play time: unreadable %s", path)
        return None
    game_id, seconds = data.get("id"), data.get("seconds")
    if not isinstance(game_id, str) or not game_id or not isinstance(seconds, int) or seconds <= 0:
        return None
    return {"id": game_id, "seconds": seconds, "title": str(data.get("title") or ""),
            "mtime": data.get("mtime")}


def _ended_at(mtime) -> datetime:
    """Naive UTC, like datetime('now') in the rest of the schema."""
    try:
        return datetime.fromisoformat(mtime).astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).replace(tzinfo=None)


def _resolve_name(conn: sqlite3.Connection, game_id: str, title: str, platform: str,
                  aliases: dict[str, str]) -> str:
    """Alias from the config; else an existing game of the same platform whose
    name matches ignoring case and punctuation (so the Vita's
    "God of War®: Ghost of Sparta" lands on "God of War - Ghost of Sparta");
    else the cleaned title (or the ID when the game has no title)."""
    if aliases.get(game_id):
        return aliases[game_id]
    name = clean_title(title) or game_id
    key = _key(name)
    rows = conn.execute(
        "SELECT DISTINCT COALESCE(canonical_name, display_name) FROM games WHERE platform = ?",
        (platform,),
    ).fetchall()
    for (existing,) in rows:
        if existing and _key(existing) == key:
            return existing
    return name


def _import_entry(conn: sqlite3.Connection, entry: dict, aliases: dict[str, str]) -> int:
    game_id, seconds = entry["id"], entry["seconds"]
    row = conn.execute("SELECT seconds FROM vita_playtime_seen WHERE game_id = ?", (game_id,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO vita_playtime_seen (game_id, seconds) VALUES (?, ?)", (game_id, seconds))
        conn.commit()
        logger.info("Vita play time baseline: %s = %ds", game_id, seconds)
        return 0
    seen = row[0]
    if seconds == seen:
        return 0
    if seconds < seen:
        conn.execute("UPDATE vita_playtime_seen SET seconds = ? WHERE game_id = ?", (seconds, game_id))
        conn.commit()
        logger.warning("Vita play time went down for %s (%d -> %d): new baseline", game_id, seen, seconds)
        return 0

    delta = seconds - seen
    platform = platform_for(game_id)
    name = _resolve_name(conn, game_id, entry["title"], platform, aliases)
    db_id = upsert_game(conn, f"vita://{game_id}", display_name=name, canonical_name=name, platform=platform)
    ended = _ended_at(entry["mtime"])
    started = ended - timedelta(seconds=delta)
    stamp = "%Y-%m-%d %H:%M:%S"
    conn.execute(
        "INSERT INTO sessions (game_id, source, started_at, ended_at, heartbeat_at, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (db_id, SOURCE, started.strftime(stamp), ended.strftime(stamp), ended.strftime(stamp), delta),
    )
    conn.execute("UPDATE vita_playtime_seen SET seconds = ? WHERE game_id = ?", (seconds, game_id))
    conn.commit()
    logger.info("Imported Vita session: %s (%ds)", name, delta)
    return 1


def import_vita_playtime(conn: sqlite3.Connection, folder: str | Path,
                         aliases: dict[str, str] | None = None) -> int:
    """Import every exported title in `folder`; returns how many sessions were created."""
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        return 0
    _ensure_state(conn)
    imported = 0
    for path in sorted(folder.glob("*.json")):
        entry = _read_entry(path)
        if entry is None or entry["id"] in IGNORED_IDS:
            continue
        imported += _import_entry(conn, entry, aliases or {})
    return imported
