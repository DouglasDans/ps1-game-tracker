from daemon.session_manager import SessionManager


def test_on_game_start_opens_session(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/mgs.cue", "duckstation")

    row = conn.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchone()
    assert row is not None
    assert row["source"] == "duckstation"


def test_on_game_start_twice_same_game_does_not_duplicate(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.on_game_start("/roms/mgs.cue", "duckstation")

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 1


def test_on_game_stop_closes_session(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.on_game_stop()

    row = conn.execute("SELECT ended_at FROM sessions").fetchone()
    assert row["ended_at"] is not None


def test_on_game_stop_without_active_session_is_noop(conn):
    manager = SessionManager(conn)
    manager.on_game_stop()  # must not raise

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 0


def test_game_switch_closes_previous_and_opens_new(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.on_game_start("/roms/crash.chd", "duckstation")

    sessions = conn.execute("SELECT * FROM sessions ORDER BY id").fetchall()
    assert len(sessions) == 2
    assert sessions[0]["ended_at"] is not None  # MGS closed
    assert sessions[1]["ended_at"] is None      # Crash open


def test_send_heartbeat_updates_active_session(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.send_heartbeat()

    row = conn.execute("SELECT heartbeat_at FROM sessions WHERE ended_at IS NULL").fetchone()
    assert row["heartbeat_at"] is not None


def test_send_heartbeat_without_session_is_noop(conn):
    manager = SessionManager(conn)
    manager.send_heartbeat()  # must not raise


def test_active_file_path_cleared_after_stop(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.on_game_stop()

    assert manager._active_file_path is None
    assert manager._active_session_id is None
