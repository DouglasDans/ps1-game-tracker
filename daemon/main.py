import logging
import queue
import sqlite3
import threading
import time
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from daemon.db import (
    crash_recovery,
    get_active_session,
    get_game_detail,
    get_games,
    get_recent_sessions,
    get_stats_summary,
    get_unenriched_games,
    init_db,
)
from daemon.enricher import enricher_loop
from daemon.session_manager import SessionManager, normalize_game_name
from daemon.watchers.lrtl import import_sessions, migrate_retroarch_games
from daemon.watchers.procfs import poll as procfs_poll
from daemon.watchers.samba import poll as samba_poll

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    config_path = ROOT / "config.toml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.toml not found at {config_path}. "
            "Copy config.toml.example and fill in your values."
        )
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def make_conn(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _is_retroarch_running() -> bool:
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmdline = (
                    (entry / "cmdline")
                    .read_bytes()
                    .decode("utf-8", errors="replace")
                    .lower()
                )
                if "retroarch" in cmdline:
                    return True
            except (OSError, PermissionError):
                continue
    except OSError:
        pass
    return False


def _migrate_canonical_names(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, canonical_name FROM games WHERE canonical_name IS NOT NULL"
    ).fetchall()
    updated = 0
    for row in rows:
        new_name = normalize_game_name(row["canonical_name"])
        if new_name != row["canonical_name"]:
            conn.execute(
                """UPDATE games SET
                       canonical_name = ?,
                       enriched_at    = CASE WHEN cover_url IS NULL THEN NULL ELSE enriched_at END
                   WHERE id = ?""",
                (new_name, row["id"]),
            )
            updated += 1
    if updated:
        conn.commit()
        logger.info("Migrated %d canonical name(s)", updated)


def polling_loop(
    manager: SessionManager,
    config: dict,
    stop: threading.Event,
    conn: sqlite3.Connection,
    enrich_q: queue.Queue,
) -> None:
    process_names = config["watchers"]["process_names"]
    extensions = config["watchers"]["rom_extensions"]
    rom_dirs = config["watchers"].get("rom_dirs", [])
    samba_rom_dirs = config["watchers"].get("samba_rom_dirs", [])
    playlist_dirs = config["watchers"].get("retroarch_playlist_dirs", [])
    interval = config["daemon"]["poll_interval_s"]

    samba_debounce = config["watchers"].get("samba_debounce_polls", 3)
    retroarch_was_running = False
    consecutive_misses = 0
    active_source: str | None = None
    last_enqueued_path: str | None = None

    while not stop.is_set():
        try:
            file_path, source = procfs_poll(process_names, extensions, rom_dirs)

            if not file_path and samba_rom_dirs:
                file_path, source = samba_poll(samba_rom_dirs, extensions)

            if file_path:
                consecutive_misses = 0
                active_source = source
                manager.on_game_start(file_path, source)
                if file_path != last_enqueued_path:
                    row = conn.execute(
                        "SELECT id, file_path, display_name, platform, canonical_name "
                        "FROM games WHERE file_path = ? AND enriched_at IS NULL AND enrichment_retries < 3",
                        (file_path,),
                    ).fetchone()
                    if row:
                        enrich_q.put(dict(row))
                    last_enqueued_path = file_path
            elif manager._active_session_id is not None:
                consecutive_misses += 1
                threshold = samba_debounce if active_source == "samba" else 1
                if consecutive_misses >= threshold:
                    manager.on_game_stop()
                    consecutive_misses = 0
                    active_source = None
            else:
                consecutive_misses = 0
                active_source = None

            manager.send_heartbeat()

            if playlist_dirs:
                retroarch_running = _is_retroarch_running()
                if retroarch_was_running and not retroarch_running:
                    n = import_sessions(conn, playlist_dirs)
                    if n:
                        logger.info("lrtl import on RetroArch exit: %d session(s)", n)
                retroarch_was_running = retroarch_running

        except Exception:
            logger.exception("Error in polling loop")
        stop.wait(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    conn = make_conn(config["daemon"]["db_path"])
    init_db(conn)

    recovered = crash_recovery(conn)
    if recovered:
        logger.info("Crash recovery: closed %d orphaned session(s)", recovered)

    _migrate_canonical_names(conn)

    playlist_dirs = config["watchers"].get("retroarch_playlist_dirs", [])
    if playlist_dirs:
        migrate_retroarch_games(conn, playlist_dirs)
        n = import_sessions(conn, playlist_dirs)
        if n:
            logger.info("lrtl startup import: %d session(s)", n)

    manager = SessionManager(conn)
    stop_event = threading.Event()
    enrich_q: queue.Queue = queue.Queue()
    app.state.conn = conn

    for game in get_unenriched_games(conn):
        enrich_q.put(game)
    logger.info("Enrichment queue: %d game(s) pending", enrich_q.qsize())

    poll_thread = threading.Thread(
        target=polling_loop,
        args=(manager, config, stop_event, conn, enrich_q),
        daemon=True,
        name="procfs-poller",
    )
    enrich_thread = threading.Thread(
        target=enricher_loop,
        args=(conn, config, stop_event, enrich_q),
        daemon=True,
        name="enricher",
    )
    poll_thread.start()
    enrich_thread.start()
    logger.info("Polling thread started (interval: %ss)", config["daemon"]["poll_interval_s"])

    yield

    stop_event.set()
    poll_thread.join(timeout=10)
    enrich_thread.join(timeout=10)
    conn.close()
    logger.info("Daemon stopped")


app = FastAPI(title="PS1 Game Tracker", lifespan=lifespan)


@app.get("/")
def index():
    html = ROOT / "web" / "index.html"
    return FileResponse(str(html))


@app.get("/sessions/active")
def active_session():
    return get_active_session(app.state.conn)


@app.get("/games")
def games():
    return get_games(app.state.conn)


@app.get("/sessions/recent")
def recent_sessions(limit: int = 20):
    return get_recent_sessions(app.state.conn, limit=limit)


@app.get("/games/{game_id}")
def game_detail(game_id: int):
    result = get_game_detail(app.state.conn, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return result


@app.get("/stats/summary")
def stats_summary():
    return get_stats_summary(app.state.conn)
