import random
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from daemon.db import heartbeat, init_db, open_session, upsert_game
from daemon.main import add_no_store_header, app, make_conn


def build_test_app(static_dir) -> FastAPI:
    app = FastAPI()
    app.middleware("http")(add_no_store_header)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


def test_api_response_has_no_store_header(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    client = TestClient(build_test_app(tmp_path))

    response = client.get("/api/ping")

    assert response.headers["cache-control"] == "no-store"


def test_static_file_response_has_no_store_header(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "app.js").write_text("console.log('hi')")
    client = TestClient(build_test_app(tmp_path))

    response = client.get("/app.js")

    assert response.headers["cache-control"] == "no-store"


# --- per-request SQLite connection ---
# One connection shared by the threadpool (plus the polling thread writing
# heartbeats) interleaves cursors: requests fired together by the Stats tab
# came back with each other's rows, or as 500s ("another row available").

STATS_PATHS = [
    "/games",
    "/stats/summary",
    "/stats/activity",
    "/stats/longest-sessions?limit=10",
    "/stats/monthly",
    "/stats/monthly-series",
]


def _seed_db(db_path):
    conn = make_conn(str(db_path))
    init_db(conn)
    random.seed(1)
    ids = [upsert_game(conn, f"/roms/g{i}.chd", f"G{i}", "PS1", f"G{i}") for i in range(30)]
    rows = []
    for _ in range(3000):
        d = date(2026, random.randint(1, 9), random.randint(1, 28))
        rows.append((random.choice(ids), "duckstation", f"{d} 20:00:00", f"{d} 21:00:00",
                     f"{d} 21:00:00", random.randint(200, 5000)))
    conn.executemany(
        "INSERT INTO sessions (game_id, source, started_at, ended_at, heartbeat_at, duration_s)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    active = open_session(conn, ids[0], "samba")
    return conn, active


def test_stats_endpoints_stay_consistent_under_concurrent_requests(tmp_path):
    db_path = tmp_path / "tracker.db"
    writer_conn, active = _seed_db(db_path)
    app.state.db_path = str(db_path)
    client = TestClient(app)
    expected = {p: client.get(p).json() for p in STATS_PATHS}

    stop = threading.Event()

    def write_heartbeats():
        while not stop.is_set():
            heartbeat(writer_conn, active)

    writer = threading.Thread(target=write_heartbeats)
    writer.start()
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [(p, pool.submit(client.get, p)) for p in STATS_PATHS * 2 * 5]
            results = [(p, f.result()) for p, f in futures]
    finally:
        stop.set()
        writer.join()
        writer_conn.close()

    assert [r.status_code for _, r in results] == [200] * len(results)
    assert all(r.json() == expected[p] for p, r in results)
