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
from daemon.watchers.procfs import poll as procfs_poll

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


def polling_loop(
    manager: SessionManager,
    config: dict,
    stop: threading.Event,
) -> None:
    process_names = config["watchers"]["process_names"]
    extensions = config["watchers"]["rom_extensions"]
    interval = config["daemon"]["poll_interval_s"]

    while not stop.is_set():
        try:
            file_path, source = procfs_poll(process_names, extensions)
            if file_path:
                manager.on_game_start(file_path, source)
            elif manager._active_session_id is not None:
                manager.on_game_stop()
            manager.send_heartbeat()
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

    manager = SessionManager(conn)
    stop_event = threading.Event()
    app.state.conn = conn

    thread = threading.Thread(
        target=polling_loop,
        args=(manager, config, stop_event),
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
