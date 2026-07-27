from daemon.session_manager import SessionManager, infer_metadata, normalize_game_name, strip_ps2_serial


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


# --- infer_metadata ---

def test_infer_metadata_display_name_is_stem():
    name, _ = infer_metadata(
        "/mnt/usb-flash/PS1/CTR - Crash Team Racing (USA).bin", "duckstation"
    )
    assert name == "CTR - Crash Team Racing"


def test_infer_metadata_platform_from_ps1_dir():
    _, platform = infer_metadata(
        "/mnt/usb-flash/Retrogaming/PS1/Crash Bandicoot (USA).bin", "duckstation"
    )
    assert platform == "PS1"


def test_infer_metadata_platform_from_psp_dir():
    _, platform = infer_metadata(
        "/mnt/usb-flash/Retrogaming/PSP/Gran Turismo (USA).iso", "ppsspp"
    )
    assert platform == "PSP"


def test_infer_metadata_platform_fallback_duckstation():
    _, platform = infer_metadata("/mnt/roms/Crash.bin", "duckstation")
    assert platform == "PS1"


def test_infer_metadata_platform_fallback_ppsspp():
    _, platform = infer_metadata("/mnt/roms/Game.iso", "ppsspp")
    assert platform == "PSP"


def test_infer_metadata_platform_from_ps2smb_dir():
    _, platform = infer_metadata("/mnt/PS2SMB/DVD/SLUS_210.50.Burnout 3 - Takedown.iso", "samba")
    assert platform == "PS2"


def test_infer_metadata_platform_fallback_samba():
    _, platform = infer_metadata("/mnt/roms/Game.iso", "samba")
    assert platform == "PS2"


def test_infer_metadata_platform_none_when_unknown():
    _, platform = infer_metadata("/mnt/roms/Game.iso", "retroarch")
    assert platform is None


# --- normalize_game_name ---

def test_normalize_strips_region():
    assert normalize_game_name("Crash Bandicoot (USA)") == "Crash Bandicoot"


def test_normalize_strips_version():
    assert normalize_game_name("Metal Gear Solid (v1.0)") == "Metal Gear Solid"


def test_normalize_strips_multiple_trailing_groups():
    assert normalize_game_name("Crash Bandicoot (USA) (v1.1)") == "Crash Bandicoot"


def test_normalize_strips_track():
    assert normalize_game_name("Dino Crisis (USA) (v1.1) (Track 1)") == "Dino Crisis"


def test_normalize_strips_disc():
    assert normalize_game_name("Gran Turismo 2 (Disc 1)") == "Gran Turismo 2"


def test_normalize_leaves_plain_title_unchanged():
    assert normalize_game_name("Gran Turismo") == "Gran Turismo"


def test_normalize_strips_bracket_tag():
    assert normalize_game_name("Ico [!]") == "Ico"


def test_normalize_strips_bracket_after_parens():
    assert normalize_game_name("Game (USA) [!]") == "Game"


def test_normalize_strips_no_intro_verbose_name():
    assert (
        normalize_game_name(
            "Tony Hawk's Pro Skater 2 v1.001 (2000)(Activision)(NTSC)(US)[!]"
        )
        == "Tony Hawk's Pro Skater 2"
    )


def test_normalize_strips_bare_version_suffix():
    assert normalize_game_name("Tony Hawk's Pro Skater 2 v1.001") == "Tony Hawk's Pro Skater 2"


def test_normalize_strips_bare_version_v1000():
    assert normalize_game_name("Looney Tunes Space Race v1.000") == "Looney Tunes Space Race"


def test_normalize_strips_version_and_parens_iteratively():
    assert normalize_game_name("Game v2.0 (USA)") == "Game"


def test_normalize_does_not_strip_uppercase_v():
    assert normalize_game_name("Grand Theft Auto V") == "Grand Theft Auto V"


# --- strip_ps2_serial ---

def test_strip_ps2_serial_removes_slus_prefix():
    assert strip_ps2_serial("SLUS_210.50.Burnout 3 - Takedown") == "Burnout 3 - Takedown"


def test_strip_ps2_serial_removes_sces_prefix():
    assert strip_ps2_serial("SCES_500.03.ICO") == "ICO"


def test_strip_ps2_serial_removes_slpm_prefix():
    assert strip_ps2_serial("SLPM_650.84.Metal Gear Solid 2") == "Metal Gear Solid 2"


def test_strip_ps2_serial_leaves_normal_filename_unchanged():
    assert strip_ps2_serial("CTR - Crash Team Racing (USA)") == "CTR - Crash Team Racing (USA)"


def test_strip_ps2_serial_leaves_ps1_filename_unchanged():
    assert strip_ps2_serial("Metal Gear Solid (Disc 1)") == "Metal Gear Solid (Disc 1)"


def test_infer_metadata_strips_ps2_serial_in_display_name(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_210.50.Burnout 3 - Takedown.iso", "samba")
    row = conn.execute("SELECT display_name, canonical_name FROM games").fetchone()
    assert row["display_name"] == "Burnout 3 - Takedown"
    assert row["canonical_name"] == "Burnout 3 - Takedown"


# --- session flip prevention ---

def test_on_game_start_multi_track_no_session_flip(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/Dino Crisis (USA) (Track 1).bin", "duckstation")
    manager.on_game_start("/roms/Dino Crisis (USA) (Track 2).bin", "duckstation")

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 1


def test_on_game_start_multi_disc_no_session_flip(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/Final Fantasy VII (USA) (Disc 1).bin", "duckstation")
    manager.on_game_start("/roms/Final Fantasy VII (USA) (Disc 2).bin", "duckstation")

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 1


def test_on_game_start_different_games_still_switches(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/Crash Bandicoot (USA).bin", "duckstation")
    manager.on_game_start("/roms/Gran Turismo (USA).bin", "duckstation")

    sessions = conn.execute("SELECT * FROM sessions ORDER BY id").fetchall()
    assert len(sessions) == 2
    assert sessions[0]["ended_at"] is not None
    assert sessions[1]["ended_at"] is None


def test_canonical_name_persisted_on_game_start(conn):
    manager = SessionManager(conn)
    manager.on_game_start("/roms/Dino Crisis (USA) (v1.1) (Track 1).bin", "duckstation")

    row = conn.execute("SELECT display_name, canonical_name FROM games").fetchone()
    assert row["display_name"] == "Dino Crisis"
    assert row["canonical_name"] == "Dino Crisis"


def test_infer_metadata_persisted_on_game_start(conn):
    manager = SessionManager(conn)
    manager.on_game_start(
        "/mnt/usb-flash/PS1/CTR - Crash Team Racing (USA).bin", "duckstation"
    )
    row = conn.execute("SELECT display_name, platform FROM games").fetchone()
    assert row["display_name"] == "CTR - Crash Team Racing"
    assert row["platform"] == "PS1"


# --- resume window (session split debounce) ---

def test_resume_within_grace_reopens_same_session(conn):
    clock = [0.0]
    manager = SessionManager(conn, resume_grace_s=35, now_fn=lambda: clock[0])
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")
    session_id = manager._active_session_id
    manager.on_game_stop()

    clock[0] = 10.0  # dentro da janela de 35s
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 1
    row = conn.execute("SELECT id, ended_at FROM sessions").fetchone()
    assert row["id"] == session_id
    assert row["ended_at"] is None


def test_resume_after_grace_expires_opens_new_session(conn):
    clock = [0.0]
    manager = SessionManager(conn, resume_grace_s=35, now_fn=lambda: clock[0])
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")
    manager.on_game_stop()

    clock[0] = 40.0  # fora da janela de 35s
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 2


def test_resume_does_not_merge_different_game(conn):
    clock = [0.0]
    manager = SessionManager(conn, resume_grace_s=35, now_fn=lambda: clock[0])
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.on_game_stop()

    clock[0] = 5.0
    manager.on_game_start("/roms/crash.chd", "duckstation")

    sessions = conn.execute("SELECT * FROM sessions ORDER BY id").fetchall()
    assert len(sessions) == 2
    assert sessions[0]["ended_at"] is not None
    assert sessions[1]["ended_at"] is None


def test_resume_requires_same_source(conn):
    clock = [0.0]
    manager = SessionManager(conn, resume_grace_s=35, now_fn=lambda: clock[0])
    manager.on_game_start("/roms/mgs.cue", "duckstation")
    manager.on_game_stop()

    clock[0] = 5.0
    manager.on_game_start("/roms/mgs.cue", "retroarch")

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 2


def test_resume_then_stop_recomputes_duration(conn):
    clock = [0.0]
    manager = SessionManager(conn, resume_grace_s=35, now_fn=lambda: clock[0])
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")
    manager.on_game_stop()

    clock[0] = 10.0
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")
    manager.on_game_stop()

    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 1
    row = conn.execute("SELECT ended_at, duration_s FROM sessions").fetchone()
    assert row["ended_at"] is not None
    assert row["duration_s"] is not None


def test_resume_heartbeat_still_works(conn):
    clock = [0.0]
    manager = SessionManager(conn, resume_grace_s=35, now_fn=lambda: clock[0])
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")
    manager.on_game_stop()

    clock[0] = 10.0
    manager.on_game_start("/mnt/PS2SMB/DVD/SLUS_205.54.Metal Gear Solid 2.iso", "samba")
    manager.send_heartbeat()

    row = conn.execute("SELECT heartbeat_at FROM sessions WHERE ended_at IS NULL").fetchone()
    assert row is not None
