import logging
import sqlite3
import threading
import time
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from daemon.db import crash_recovery, get_active_session, get_games, init_db
from daemon.session_manager import SessionManager
from daemon.watchers.lrtl import import_sessions
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


def polling_loop(
    manager: SessionManager,
    config: dict,
    stop: threading.Event,
    conn: sqlite3.Connection,
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

    while not stop.is_set():
        try:
            file_path, source = procfs_poll(process_names, extensions, rom_dirs)

            if not file_path and samba_rom_dirs:
                file_path, source = samba_poll(samba_rom_dirs, extensions)

            if file_path:
                consecutive_misses = 0
                active_source = source
                manager.on_game_start(file_path, source)
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

    playlist_dirs = config["watchers"].get("retroarch_playlist_dirs", [])
    if playlist_dirs:
        n = import_sessions(conn, playlist_dirs)
        if n:
            logger.info("lrtl startup import: %d session(s)", n)

    manager = SessionManager(conn)
    stop_event = threading.Event()
    app.state.conn = conn

    thread = threading.Thread(
        target=polling_loop,
        args=(manager, config, stop_event, conn),
        daemon=True,
        name="procfs-poller",
    )
    thread.start()
    logger.info("Polling thread started (interval: %ss)", config["daemon"]["poll_interval_s"])

    yield

    stop_event.set()
    thread.join(timeout=10)
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
