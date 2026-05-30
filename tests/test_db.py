from daemon.db import (
    upsert_game,
    open_session,
    close_session,
    heartbeat,
    crash_recovery,
    get_active_session,
    get_games,
    get_unenriched_games,
    update_game_enrichment,
    increment_enrichment_retries,
)


def test_upsert_game_creates_new_game(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    assert game_id is not None


def test_upsert_game_returns_same_id_for_same_path(conn):
    id1 = upsert_game(conn, "/roms/mgs.cue")
    id2 = upsert_game(conn, "/roms/mgs.cue")
    assert id1 == id2


def test_open_session_creates_session(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    assert session_id is not None


def test_close_session_sets_ended_at_and_duration(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    close_session(conn, session_id)

    row = conn.execute(
        "SELECT ended_at, duration_s FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    assert row["ended_at"] is not None
    assert row["duration_s"] >= 0


def test_close_session_abnormal_flag(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    close_session(conn, session_id, abnormal=True)

    row = conn.execute(
        "SELECT ended_abnormally FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    assert row["ended_abnormally"] == 1


def test_heartbeat_updates_timestamp(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    heartbeat(conn, session_id)

    row = conn.execute(
        "SELECT heartbeat_at FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    assert row["heartbeat_at"] is not None


def test_crash_recovery_closes_orphaned_sessions(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")

    conn.execute(
        "UPDATE sessions SET heartbeat_at = '2020-01-01 00:00:00' WHERE id = ?",
        (session_id,),
    )
    conn.commit()

    recovered = crash_recovery(conn)
    assert recovered == 1

    row = conn.execute(
        "SELECT ended_at, ended_abnormally FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    assert row["ended_at"] is not None
    assert row["ended_abnormally"] == 1


def test_crash_recovery_ignores_sessions_without_heartbeat(conn):
    # Sessions that never got a heartbeat (crashed before first poll) are also recovered
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    conn.execute(
        "UPDATE sessions SET heartbeat_at = NULL WHERE id = ?", (session_id,)
    )
    conn.commit()

    recovered = crash_recovery(conn)
    assert recovered == 1


def test_crash_recovery_does_not_close_recent_sessions(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    heartbeat(conn, session_id)

    crash_recovery(conn)

    row = conn.execute(
        "SELECT ended_at FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    assert row["ended_at"] is None


def test_get_active_session_returns_none_when_no_session(conn):
    assert get_active_session(conn) is None


def test_get_active_session_returns_open_session(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    open_session(conn, game_id, "duckstation")

    session = get_active_session(conn)
    assert session is not None
    assert session["source"] == "duckstation"
    assert session["file_path"] == "/roms/mgs.cue"


def test_get_active_session_returns_none_after_close(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    close_session(conn, session_id)

    assert get_active_session(conn) is None


def test_get_games_returns_empty_list_with_no_completed_sessions(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    open_session(conn, game_id, "duckstation")  # session still open

    assert get_games(conn) == []


def test_get_games_returns_game_after_session_closes(conn):
    game_id = upsert_game(conn, "/roms/mgs.cue")
    session_id = open_session(conn, game_id, "duckstation")
    close_session(conn, session_id)

    games = get_games(conn)
    assert len(games) == 1
    assert games[0]["file_path"] == "/roms/mgs.cue"
    assert games[0]["session_count"] == 1


def test_get_games_aggregates_multi_track_playtime(conn):
    id1 = upsert_game(conn, "/roms/Dino Crisis (Track 1).bin", "Dino Crisis", "PS1", "Dino Crisis")
    id2 = upsert_game(conn, "/roms/Dino Crisis (Track 2).bin", "Dino Crisis", "PS1", "Dino Crisis")

    s1 = open_session(conn, id1, "duckstation")
    close_session(conn, s1)
    conn.execute("UPDATE sessions SET duration_s = 100 WHERE id = ?", (s1,))

    s2 = open_session(conn, id2, "duckstation")
    close_session(conn, s2)
    conn.execute("UPDATE sessions SET duration_s = 200 WHERE id = ?", (s2,))
    conn.commit()

    games = get_games(conn)
    assert len(games) == 1
    assert games[0]["display_name"] == "Dino Crisis"
    assert games[0]["total_seconds"] == 300
    assert games[0]["session_count"] == 2


def test_get_unenriched_games_returns_unenriched(conn):
    upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "Metal Gear Solid")
    games = get_unenriched_games(conn)
    assert len(games) == 1
    assert games[0]["file_path"] == "/roms/mgs.chd"


def test_get_unenriched_games_skips_already_enriched(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "Metal Gear Solid")
    update_game_enrichment(conn, game_id)
    assert get_unenriched_games(conn) == []


def test_get_unenriched_games_skips_exhausted_retries(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "Metal Gear Solid")
    for _ in range(3):
        increment_enrichment_retries(conn, game_id)
    assert get_unenriched_games(conn) == []


def test_update_game_enrichment_sets_enriched_at_and_fields(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd")
    update_game_enrichment(conn, game_id, display_name="Metal Gear Solid", igdb_id=375, release_year=1998)
    row = conn.execute(
        "SELECT enriched_at, display_name, igdb_id, release_year FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()
    assert row["enriched_at"] is not None
    assert row["display_name"] == "Metal Gear Solid"
    assert row["igdb_id"] == 375
    assert row["release_year"] == 1998


def test_update_game_enrichment_does_not_overwrite_existing_values_with_none(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd", display_name="Old Name")
    update_game_enrichment(conn, game_id, display_name=None)
    row = conn.execute("SELECT display_name FROM games WHERE id = ?", (game_id,)).fetchone()
    assert row["display_name"] == "Old Name"


def test_increment_enrichment_retries(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd")
    increment_enrichment_retries(conn, game_id)
    increment_enrichment_retries(conn, game_id)
    row = conn.execute(
        "SELECT enrichment_retries FROM games WHERE id = ?", (game_id,)
    ).fetchone()
    assert row["enrichment_retries"] == 2
