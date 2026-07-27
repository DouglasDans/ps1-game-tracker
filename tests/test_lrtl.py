import json
from pathlib import Path

from daemon.watchers.lrtl import (
    _load_playlist_map,
    _parse_lrtl,
    _platform_from_db_name,
    import_sessions,
    migrate_retroarch_games,
)

_LRTL = {
    "version": "1.0",
    "runtime": "0:30:00",
    "last_played": "2026-05-23 15:00:00",
}


def _write_playlist(base_dir: Path, items: list[dict], filename: str = "Sony - PlayStation.lpl") -> None:
    (base_dir / filename).write_text(json.dumps({"version": "1.5", "items": items}))


def _ps1_item(label: str, path: str = "") -> dict:
    return {
        "path": path or f"/mnt/roms/{label}.chd",
        "label": label,
        "core_path": "DETECT",
        "core_name": "DETECT",
        "crc32": "00000000|crc",
        "db_name": "Sony - PlayStation.lpl",
    }


def _megadrive_item(label: str, path: str = "") -> dict:
    return {
        "path": path or f"/mnt/roms/{label}.md",
        "label": label,
        "core_path": "DETECT",
        "core_name": "DETECT",
        "crc32": "00000000|crc",
        "db_name": "Sega - Mega Drive - Genesis.lpl",
    }


# --- _parse_lrtl ---

def test_parse_lrtl_extracts_runtime_and_last_played():
    result = _parse_lrtl(_LRTL)
    assert result is not None
    runtime_s, last_played = result
    assert runtime_s == 1800
    assert last_played.year == 2026
    assert last_played.hour == 15


def test_parse_lrtl_handles_hours():
    data = {"version": "1.0", "runtime": "1:05:30", "last_played": "2026-05-23 10:00:00"}
    runtime_s, _ = _parse_lrtl(data)
    assert runtime_s == 3600 + 5 * 60 + 30


def test_parse_lrtl_returns_none_for_empty_dict():
    assert _parse_lrtl({}) is None


def test_parse_lrtl_returns_none_for_missing_keys():
    assert _parse_lrtl({"runtime": "0:30:00"}) is None
    assert _parse_lrtl({"last_played": "2026-05-23 15:00:00"}) is None


def test_parse_lrtl_returns_none_for_zero_runtime():
    data = {"version": "1.0", "runtime": "0:00:00", "last_played": "2026-05-23 15:00:00"}
    assert _parse_lrtl(data) is None


def test_parse_lrtl_returns_none_for_malformed_runtime():
    data = {"version": "1.0", "runtime": "invalid", "last_played": "2026-05-23 15:00:00"}
    assert _parse_lrtl(data) is None


# --- _platform_from_db_name ---

def test_platform_from_db_name_ps1():
    assert _platform_from_db_name("Sony - PlayStation.lpl") == "PS1"


def test_platform_from_db_name_psp():
    assert _platform_from_db_name("Sony - PlayStation Portable.lpl") == "PSP"


def test_platform_from_db_name_ps2():
    assert _platform_from_db_name("Sony - PlayStation 2.lpl") == "PS2"


def test_platform_from_db_name_dreamcast():
    assert _platform_from_db_name("Sega - Dreamcast.lpl") == "Dreamcast"


def test_platform_from_db_name_snes():
    assert _platform_from_db_name("Nintendo - Super Nintendo Entertainment System.lpl") == "SNES"


def test_platform_from_db_name_fallback_strips_brand():
    assert _platform_from_db_name("Atari - 2600.lpl") == "2600"


def test_platform_from_db_name_ds():
    assert _platform_from_db_name("Nintendo - Nintendo DS.lpl") == "DS"


def test_platform_from_db_name_3ds():
    assert _platform_from_db_name("Nintendo - Nintendo 3DS.lpl") == "3DS"


def test_platform_from_db_name_ps_vita():
    assert _platform_from_db_name("Sony - PlayStation Vita.lpl") == "PS Vita"


def test_platform_from_db_name_wii():
    assert _platform_from_db_name("Nintendo - Wii.lpl") == "Wii"


def test_platform_from_db_name_switch():
    assert _platform_from_db_name("Nintendo - Nintendo Switch.lpl") == "Switch"


def test_platform_from_db_name_unknown_no_separator_returns_stem():
    assert _platform_from_db_name("Unknown.lpl") == "Unknown"


def test_platform_from_db_name_empty_returns_none():
    assert _platform_from_db_name("") is None


# --- _load_playlist_map ---

def test_load_playlist_map_returns_game_with_platform(tmp_path):
    _write_playlist(tmp_path, [_ps1_item("Ico")])
    result = _load_playlist_map([str(tmp_path)])
    assert result.get("ico") == "PS1"


def test_load_playlist_map_normalizes_label(tmp_path):
    _write_playlist(tmp_path, [_ps1_item("Ico (USA)")])
    result = _load_playlist_map([str(tmp_path)])
    assert result.get("ico") == "PS1"


def test_load_playlist_map_indexes_by_path_stem(tmp_path):
    item = _ps1_item("Ico", path="/mnt/roms/Ico (USA).chd")
    item["label"] = ""
    _write_playlist(tmp_path, [item])
    result = _load_playlist_map([str(tmp_path)])
    assert result.get("ico") == "PS1"


def test_load_playlist_map_empty_dir(tmp_path):
    assert _load_playlist_map([str(tmp_path)]) == {}


def test_load_playlist_map_skips_corrupt_playlist(tmp_path):
    (tmp_path / "bad.lpl").write_text("not json {{{")
    assert _load_playlist_map([str(tmp_path)]) == {}


# --- import_sessions ---

def test_import_sessions_creates_session_for_new_content(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 1
    row = conn.execute(
        "SELECT duration_s, source FROM sessions WHERE source = 'retroarch'"
    ).fetchone()
    assert row["duration_s"] == 1800
    assert row["source"] == "retroarch"


def test_import_sessions_sets_platform_from_playlist(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Sonic the Hedgehog 2.lrtl").write_text(json.dumps(_LRTL))
    _write_playlist(tmp_path, [_megadrive_item("Sonic the Hedgehog 2")], filename="Sega - Mega Drive - Genesis.lpl")

    import_sessions(conn, [str(tmp_path)])

    row = conn.execute("SELECT platform FROM games").fetchone()
    assert row["platform"] == "Mega Drive"


def test_import_sessions_skips_pcsx_rearmed_core(conn, tmp_path):
    logs_dir = tmp_path / "logs" / "PCSX-ReARMed"
    logs_dir.mkdir(parents=True)
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 0
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_import_sessions_skips_beetle_psx_hw_core(conn, tmp_path):
    logs_dir = tmp_path / "logs" / "Beetle PSX HW"
    logs_dir.mkdir(parents=True)
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 0
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_import_sessions_skips_swanstation_core(conn, tmp_path):
    logs_dir = tmp_path / "logs" / "SwanStation"
    logs_dir.mkdir(parents=True)
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 0
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_import_sessions_imports_non_ps1_core_normally(conn, tmp_path):
    logs_dir = tmp_path / "logs" / "Flycast"
    logs_dir.mkdir(parents=True)
    (logs_dir / "Shenmue.lrtl").write_text(json.dumps(_LRTL))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 1
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_import_sessions_ps1_core_skip_does_not_depend_on_playlist(conn, tmp_path):
    # Same title also listed under a non-PS1 playlist (name collision) — core folder wins.
    logs_dir = tmp_path / "logs" / "PCSX-ReARMed"
    logs_dir.mkdir(parents=True)
    (logs_dir / "Dino Crisis.lrtl").write_text(json.dumps(_LRTL))
    _write_playlist(tmp_path, [_megadrive_item("Dino Crisis")], filename="Sega - Mega Drive - Genesis.lpl")

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 0
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_import_sessions_imports_game_not_in_playlist(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "cube.lrtl").write_text(json.dumps(_LRTL))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 1
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_import_sessions_skips_already_imported(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL))

    import_sessions(conn, [str(tmp_path)])
    n = import_sessions(conn, [str(tmp_path)])

    assert n == 0
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_import_sessions_skips_nonexistent_dir(conn):
    assert import_sessions(conn, ["/nonexistent/path"]) == 0


def test_import_sessions_handles_corrupt_lrtl(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Broken.lrtl").write_text("not valid json {{{")
    assert import_sessions(conn, [str(tmp_path)]) == 0


def test_import_sessions_normalizes_canonical_name(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Ico (USA).lrtl").write_text(json.dumps(_LRTL))

    import_sessions(conn, [str(tmp_path)])

    row = conn.execute("SELECT canonical_name FROM games").fetchone()
    assert row["canonical_name"] == "Ico"


def test_import_sessions_resolves_platform_case_insensitive(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Sonic the Hedgehog 2 (World).lrtl").write_text(json.dumps(_LRTL))
    (tmp_path / "Sega - Mega Drive - Genesis.lpl").write_text(
        json.dumps({"version": "1.5", "items": [_megadrive_item("Sonic The Hedgehog 2 (World)")]})
    )

    import_sessions(conn, [str(tmp_path)])

    row = conn.execute("SELECT platform FROM games").fetchone()
    assert row["platform"] == "Mega Drive"


def test_import_sessions_skips_zero_runtime(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Empty.lrtl").write_text(
        json.dumps({"version": "1.0", "runtime": "0:00:00", "last_played": "2026-05-23 00:00:00"})
    )
    assert import_sessions(conn, [str(tmp_path)]) == 0


# --- migrate_retroarch_games ---

def _insert_retroarch_game(conn, file_path: str, display_name: str, canonical_name: str | None = None, platform: str | None = None) -> int:
    conn.execute(
        "INSERT INTO games (file_path, display_name, canonical_name, platform) VALUES (?, ?, ?, ?)",
        (file_path, display_name, canonical_name, platform),
    )
    conn.commit()
    return conn.execute("SELECT id FROM games WHERE file_path = ?", (file_path,)).fetchone()[0]


def _insert_session(conn, game_id: int) -> int:
    conn.execute(
        "INSERT INTO sessions (game_id, source, started_at, ended_at, heartbeat_at, duration_s) "
        "VALUES (?, 'retroarch', '2026-01-01 10:00:00', '2026-01-01 11:00:00', '2026-01-01 11:00:00', 3600)",
        (game_id,),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_migrate_normalizes_verbose_name(conn, tmp_path):
    ugly = "Tony Hawk's Pro Skater 2 v1.001 (2000)(Activision)(NTSC)(US)[!]"
    _insert_retroarch_game(conn, f"retroarch://{ugly}", ugly, ugly)
    _write_playlist(tmp_path, [_ps1_item("Tony Hawk's Pro Skater 2 v1.001 (2000)(Activision)(NTSC)(US)[!]")])

    migrate_retroarch_games(conn, [str(tmp_path)])

    row = conn.execute("SELECT file_path, display_name, canonical_name FROM games").fetchone()
    assert row["display_name"] == "Tony Hawk's Pro Skater 2"
    assert row["canonical_name"] == "Tony Hawk's Pro Skater 2"
    assert row["file_path"] == "retroarch://Tony Hawk's Pro Skater 2"


def test_migrate_sets_platform_from_playlist(conn, tmp_path):
    _insert_retroarch_game(conn, "retroarch://Ico", "Ico", "Ico")
    _write_playlist(tmp_path, [_ps1_item("Ico")])

    migrate_retroarch_games(conn, [str(tmp_path)])

    row = conn.execute("SELECT platform FROM games").fetchone()
    assert row["platform"] == "PS1"


def test_migrate_skips_game_not_in_playlist(conn, tmp_path):
    game_id = _insert_retroarch_game(conn, "retroarch://cube", "cube", "cube")
    _insert_session(conn, game_id)
    (tmp_path / "Sony - PlayStation.lpl").write_text(json.dumps({"version": "1.5", "items": []}))

    migrate_retroarch_games(conn, [str(tmp_path)])

    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_migrate_merges_sessions_on_normalization_collision(conn, tmp_path):
    ugly = "Ico (USA) [!]"
    old_id = _insert_retroarch_game(conn, f"retroarch://{ugly}", ugly, ugly)
    new_id = _insert_retroarch_game(conn, "retroarch://Ico", "Ico", "Ico")
    _insert_session(conn, old_id)
    _insert_session(conn, new_id)
    _write_playlist(tmp_path, [_ps1_item("Ico (USA) [!]")])

    migrate_retroarch_games(conn, [str(tmp_path)])

    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    remaining = conn.execute("SELECT id FROM games").fetchone()[0]
    assert conn.execute("SELECT COUNT(*) FROM sessions WHERE game_id = ?", (remaining,)).fetchone()[0] == 2


def test_migrate_does_not_touch_non_retroarch_games(conn, tmp_path):
    conn.execute(
        "INSERT INTO games (file_path, display_name, platform) VALUES (?, ?, ?)",
        ("/mnt/roms/PS1/CTR.bin", "CTR", "PS1"),
    )
    conn.commit()
    (tmp_path / "Sony - PlayStation.lpl").write_text(json.dumps({"version": "1.5", "items": []}))

    migrate_retroarch_games(conn, [str(tmp_path)])

    row = conn.execute("SELECT file_path, display_name FROM games").fetchone()
    assert row["file_path"] == "/mnt/roms/PS1/CTR.bin"
    assert row["display_name"] == "CTR"


def test_migrate_is_idempotent(conn, tmp_path):
    _insert_retroarch_game(conn, "retroarch://Ico (USA)", "Ico (USA)", "Ico (USA)")
    _write_playlist(tmp_path, [_ps1_item("Ico (USA)")])

    migrate_retroarch_games(conn, [str(tmp_path)])
    migrate_retroarch_games(conn, [str(tmp_path)])

    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    row = conn.execute("SELECT display_name FROM games").fetchone()
    assert row["display_name"] == "Ico"
