import logging
import queue
import sqlite3
import threading
import time
import tomllib
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from daemon.db import (
    crash_recovery,
    get_active_session,
    get_activity_stats,
    get_game_detail,
    get_games,
    get_longest_sessions,
    get_monthly_series,
    get_monthly_stats,
    get_stats_summary,
    get_unenriched_games,
    init_db,
    reset_all_enrichment,
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
                file_path, source = samba_poll(samba_rom_dirs)

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
    db_path = config["daemon"]["db_path"]
    # This connection is owned by the startup code and then by the polling
    # thread alone. The enricher and every request open their own (see
    # get_conn): a sqlite3 connection used from several threads at once
    # interleaves cursors — concurrent requests got each other's rows or 500s.
    conn = make_conn(db_path)
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

    resume_grace_s = config["watchers"].get("session_resume_grace_s", 35)
    manager = SessionManager(conn, resume_grace_s=resume_grace_s)
    stop_event = threading.Event()
    enrich_q: queue.Queue = queue.Queue()
    app.state.db_path = db_path
    app.state.enrich_q = enrich_q

    for game in get_unenriched_games(conn):
        enrich_q.put(game)
    logger.info("Enrichment queue: %d game(s) pending", enrich_q.qsize())

    enrich_conn = make_conn(db_path)
    poll_thread = threading.Thread(
        target=polling_loop,
        args=(manager, config, stop_event, conn, enrich_q),
        daemon=True,
        name="procfs-poller",
    )
    enrich_thread = threading.Thread(
        target=enricher_loop,
        args=(enrich_conn, config, stop_event, enrich_q),
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
    enrich_conn.close()
    conn.close()
    logger.info("Daemon stopped")


async def add_no_store_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = make_conn(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


app = FastAPI(title="PS1 Game Tracker", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])
app.middleware("http")(add_no_store_header)


@app.get("/sessions/active")
def active_session(conn: sqlite3.Connection = Depends(get_conn)):
    return get_active_session(conn)


@app.get("/games")
def games(conn: sqlite3.Connection = Depends(get_conn)):
    return get_games(conn)


@app.get("/games/{game_id}")
def game_detail(game_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    result = get_game_detail(conn, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return result


@app.get("/stats/summary")
def stats_summary(conn: sqlite3.Connection = Depends(get_conn)):
    return get_stats_summary(conn)


@app.get("/stats/activity")
def stats_activity(conn: sqlite3.Connection = Depends(get_conn)):
    return get_activity_stats(conn)


@app.get("/stats/monthly")
def stats_monthly(conn: sqlite3.Connection = Depends(get_conn)):
    return get_monthly_stats(conn)


@app.get("/stats/monthly-series")
def stats_monthly_series(conn: sqlite3.Connection = Depends(get_conn)):
    return get_monthly_series(conn)


@app.get("/stats/longest-sessions")
def stats_longest_sessions(limit: int = 10, conn: sqlite3.Connection = Depends(get_conn)):
    return get_longest_sessions(conn, limit=limit)


@app.post("/admin/reset-enrichment")
def admin_reset_enrichment(conn: sqlite3.Connection = Depends(get_conn)):
    n = reset_all_enrichment(conn)
    for game in get_unenriched_games(conn):
        app.state.enrich_q.put(game)
    queued = app.state.enrich_q.qsize()
    return {"reset": n, "queued": queued}


app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="static")
