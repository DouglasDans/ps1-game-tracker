from daemon.db import (
    upsert_game,
    open_session,
    close_session,
    heartbeat,
    crash_recovery,
    get_active_session,
    get_game_detail,
    get_games,
    get_stats_summary,
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


# --- get_game_detail ---

def test_get_game_detail_returns_none_for_nonexistent_id(conn):
    assert get_game_detail(conn, 999) is None


def test_get_game_detail_returns_game_data(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd", "Metal Gear Solid", "PS1", "Metal Gear Solid")
    update_game_enrichment(conn, game_id, genre="Action", release_year=1998)
    session_id = open_session(conn, game_id, "duckstation")
    close_session(conn, session_id)
    conn.execute("UPDATE sessions SET duration_s = 3600 WHERE id = ?", (session_id,))
    conn.commit()

    result = get_game_detail(conn, game_id)
    assert result is not None
    assert result["display_name"] == "Metal Gear Solid"
    assert result["platform"] == "PS1"
    assert result["genre"] == "Action"
    assert result["release_year"] == 1998
    assert result["total_seconds"] == 3600
    assert result["session_count"] == 1
    assert len(result["sessions"]) == 1
    assert result["sessions"][0]["source"] == "duckstation"
    assert result["sessions"][0]["duration_s"] == 3600


def test_get_game_detail_excludes_open_sessions(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "MGS")
    open_session(conn, game_id, "duckstation")

    result = get_game_detail(conn, game_id)
    assert result is not None
    assert result["session_count"] == 0
    assert result["sessions"] == []


def test_get_game_detail_aggregates_multi_track(conn):
    id1 = upsert_game(conn, "/roms/CTR (Track 1).bin", "CTR", "PS1", "Crash Team Racing")
    id2 = upsert_game(conn, "/roms/CTR (Track 2).bin", "CTR", "PS1", "Crash Team Racing")

    s1 = open_session(conn, id1, "duckstation")
    close_session(conn, s1)
    conn.execute("UPDATE sessions SET duration_s = 1000 WHERE id = ?", (s1,))

    s2 = open_session(conn, id2, "duckstation")
    close_session(conn, s2)
    conn.execute("UPDATE sessions SET duration_s = 2000 WHERE id = ?", (s2,))
    conn.commit()

    result = get_game_detail(conn, id1)
    assert result["total_seconds"] == 3000
    assert result["session_count"] == 2
    assert len(result["sessions"]) == 2


def test_get_game_detail_sessions_ordered_newest_first(conn):
    game_id = upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "MGS")

    s1 = open_session(conn, game_id, "duckstation")
    close_session(conn, s1)
    conn.execute(
        "UPDATE sessions SET started_at = '2026-01-01 10:00:00', duration_s = 100 WHERE id = ?",
        (s1,),
    )
    s2 = open_session(conn, game_id, "duckstation")
    close_session(conn, s2)
    conn.execute(
        "UPDATE sessions SET started_at = '2026-02-01 10:00:00', duration_s = 200 WHERE id = ?",
        (s2,),
    )
    conn.commit()

    result = get_game_detail(conn, game_id)
    assert result["sessions"][0]["started_at"] == "2026-02-01 10:00:00"
    assert result["sessions"][1]["started_at"] == "2026-01-01 10:00:00"


# --- get_stats_summary ---

def test_get_stats_summary_empty_db(conn):
    result = get_stats_summary(conn)
    assert result["total_seconds"] == 0
    assert result["total_games"] == 0
    assert result["most_played"] is None
    assert result["longest_session"] is None
    assert result["by_platform"] == []


def test_get_stats_summary_total_seconds(conn):
    id1 = upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "MGS")
    id2 = upsert_game(conn, "/roms/ctr.chd", "CTR", "PS1", "CTR")

    s1 = open_session(conn, id1, "duckstation")
    close_session(conn, s1)
    conn.execute("UPDATE sessions SET duration_s = 1000 WHERE id = ?", (s1,))
    s2 = open_session(conn, id2, "duckstation")
    close_session(conn, s2)
    conn.execute("UPDATE sessions SET duration_s = 2000 WHERE id = ?", (s2,))
    conn.commit()

    result = get_stats_summary(conn)
    assert result["total_seconds"] == 3000
    assert result["total_games"] == 2


def test_get_stats_summary_most_played(conn):
    id1 = upsert_game(conn, "/roms/mgs.chd", "Metal Gear Solid", "PS1", "Metal Gear Solid")
    id2 = upsert_game(conn, "/roms/ctr.chd", "Crash Team Racing", "PS1", "Crash Team Racing")

    s1 = open_session(conn, id1, "duckstation")
    close_session(conn, s1)
    conn.execute("UPDATE sessions SET duration_s = 5000 WHERE id = ?", (s1,))
    s2 = open_session(conn, id2, "duckstation")
    close_session(conn, s2)
    conn.execute("UPDATE sessions SET duration_s = 1000 WHERE id = ?", (s2,))
    conn.commit()

    result = get_stats_summary(conn)
    assert result["most_played"]["display_name"] == "Metal Gear Solid"
    assert result["most_played"]["total_seconds"] == 5000


def test_get_stats_summary_longest_session(conn):
    id1 = upsert_game(conn, "/roms/mgs.chd", "Metal Gear Solid", "PS1", "Metal Gear Solid")
    id2 = upsert_game(conn, "/roms/ctr.chd", "Crash Team Racing", "PS1", "Crash Team Racing")

    s1 = open_session(conn, id1, "duckstation")
    close_session(conn, s1)
    conn.execute("UPDATE sessions SET duration_s = 500 WHERE id = ?", (s1,))
    s2 = open_session(conn, id2, "duckstation")
    close_session(conn, s2)
    conn.execute("UPDATE sessions SET duration_s = 9000 WHERE id = ?", (s2,))
    conn.commit()

    result = get_stats_summary(conn)
    assert result["longest_session"]["duration_s"] == 9000
    assert result["longest_session"]["display_name"] == "Crash Team Racing"


def test_get_stats_summary_by_platform(conn):
    id1 = upsert_game(conn, "/roms/mgs.chd", "MGS", "PS1", "MGS")
    id2 = upsert_game(conn, "/roms/gt2.chd", "GT2", "PS2", "GT2")

    s1 = open_session(conn, id1, "duckstation")
    close_session(conn, s1)
    conn.execute("UPDATE sessions SET duration_s = 6000 WHERE id = ?", (s1,))
    s2 = open_session(conn, id2, "samba")
    close_session(conn, s2)
    conn.execute("UPDATE sessions SET duration_s = 4000 WHERE id = ?", (s2,))
    conn.commit()

    result = get_stats_summary(conn)
    platforms = {p["platform"]: p for p in result["by_platform"]}
    assert platforms["PS1"]["total_seconds"] == 6000
    assert platforms["PS1"]["pct"] == 60
    assert platforms["PS2"]["total_seconds"] == 4000
    assert platforms["PS2"]["pct"] == 40
