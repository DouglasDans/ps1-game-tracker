"""Vita play time importer (rules VT-01..VT-14).

The vita-sync service on the Pi exports one JSON per game ({id, seconds, title,
mtime}); this watcher turns the growth of that running total into sessions."""

import json

from daemon.db import upsert_game
from daemon.watchers.vita import (
    clean_title,
    import_vita_playtime,
    platform_for,
)


def export(folder, game_id, seconds, title="", mtime="2026-11-24T23:30:00+00:00"):
    (folder / f"{game_id}.json").write_text(
        json.dumps({"id": game_id, "seconds": seconds, "title": title, "mtime": mtime}),
        encoding="utf-8")


def sessions(conn):
    return [dict(r) for r in conn.execute(
        "SELECT g.file_path, g.display_name, g.canonical_name, g.platform, s.source, "
        "s.started_at, s.ended_at, s.heartbeat_at, s.duration_s, s.ended_abnormally "
        "FROM sessions s JOIN games g ON g.id = s.game_id ORDER BY s.id")]


def test_vt01_first_reading_is_only_the_baseline(conn, tmp_path):
    export(tmp_path, "UCUS98632", 6259, "Gran Turismo®")
    assert import_vita_playtime(conn, tmp_path) == 0
    assert sessions(conn) == []


def test_vt05_growth_becomes_one_session_ending_at_the_file_date(conn, tmp_path):
    export(tmp_path, "UCUS98632", 6259, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98632", 6259 + 1800, "Gran Turismo®", mtime="2026-11-25T01:00:00+00:00")
    assert import_vita_playtime(conn, tmp_path) == 1
    (session,) = sessions(conn)
    assert session["source"] == "vita"
    assert session["duration_s"] == 1800
    assert session["started_at"] == "2026-11-25 00:30:00"     # naive UTC, like datetime('now')
    assert session["ended_at"] == session["heartbeat_at"] == "2026-11-25 01:00:00"
    assert session["ended_abnormally"] == 0


def test_vt14_running_twice_creates_nothing_new(conn, tmp_path):
    export(tmp_path, "UCUS98632", 100, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98632", 700, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    assert import_vita_playtime(conn, tmp_path) == 0
    assert len(sessions(conn)) == 1


def test_vt10_a_counter_that_goes_down_is_a_new_baseline_not_a_negative_session(conn, tmp_path):
    export(tmp_path, "UCUS98632", 5000, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98632", 120, "Gran Turismo®")          # plugin data reset
    assert import_vita_playtime(conn, tmp_path) == 0
    export(tmp_path, "UCUS98632", 420, "Gran Turismo®")
    assert import_vita_playtime(conn, tmp_path) == 1
    assert sessions(conn)[0]["duration_s"] == 300


def test_vt12_short_sessions_are_still_recorded(conn, tmp_path):
    export(tmp_path, "UCUS98632", 100, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98632", 130, "Gran Turismo®")
    assert import_vita_playtime(conn, tmp_path) == 1


def test_vt02_system_apps_are_never_imported(conn, tmp_path):
    for app in ("VITASHELL", "EMU4VPLUS", "AUTOPLUG2", "TPLG00001", "VXMB00001", "VXMBUPDTR",
                "UCJS10041", "VITADBDLD", "SKGD3PL0Y", "XYZZ00002", "PCSI00011"):
        export(tmp_path, app, 100, "x")
    import_vita_playtime(conn, tmp_path)
    for app in ("VITASHELL", "EMU4VPLUS", "AUTOPLUG2", "TPLG00001", "VXMB00001", "VXMBUPDTR",
                "UCJS10041", "VITADBDLD", "SKGD3PL0Y", "XYZZ00002", "PCSI00011"):
        export(tmp_path, app, 9000, "x")
    assert import_vita_playtime(conn, tmp_path) == 0
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_vt03_platform_comes_from_the_id_prefix():
    assert platform_for("PCSA00011") == "PS Vita"
    assert platform_for("PCSE00791") == "PS Vita"
    assert platform_for("ULUS10160") == "PSP"
    assert platform_for("UCUS98632") == "PSP"
    assert platform_for("SCUS94455") == "PS1"
    assert platform_for("SLUS01369") == "PS1"
    assert platform_for("SCES00000") == "PS1"
    assert platform_for("GTASA0000") == "PS Vita"      # homebrew runs on the Vita
    assert platform_for("SHIPOFHAR") == "PS Vita"


def test_vt06_a_new_game_enters_with_its_cleaned_title_and_platform(conn, tmp_path):
    export(tmp_path, "ULUS10380", 100, "LEGO® Batman™: The Videogame")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "ULUS10380", 700, "LEGO® Batman™: The Videogame")
    import_vita_playtime(conn, tmp_path)
    (session,) = sessions(conn)
    assert (session["file_path"], session["platform"]) == ("vita://ULUS10380", "PSP")
    assert session["display_name"] == session["canonical_name"] == "LEGO Batman: The Videogame"


def test_vt06_missing_title_falls_back_to_the_id(conn, tmp_path):
    export(tmp_path, "GTASA0000", 10, "")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "GTASA0000", 400, "")
    import_vita_playtime(conn, tmp_path)
    assert sessions(conn)[0]["canonical_name"] == "GTASA0000"


def test_vt07_title_cleaning_removes_trademarks_and_extra_spaces():
    assert clean_title("Gran Turismo®") == "Gran Turismo"
    assert clean_title("CTR: Crash Team Racing™") == "CTR: Crash Team Racing"
    assert clean_title("  Crash™   Tag Team Racing ") == "Crash Tag Team Racing"


def test_vt08_it_joins_an_existing_game_of_the_same_platform_by_name(conn, tmp_path):
    existing = upsert_game(conn, "/mnt/usb-flash/Retrogaming/PSP/God of War - Ghost of Sparta (USA).chd",
                           display_name="God of War: Ghost of Sparta",
                           canonical_name="God of War - Ghost of Sparta", platform="PSP")
    export(tmp_path, "UCUS98737", 100, "God of War®: Ghost of Sparta")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98737", 1000, "God of War®: Ghost of Sparta")
    import_vita_playtime(conn, tmp_path)
    (session,) = sessions(conn)
    assert session["canonical_name"] == "God of War - Ghost of Sparta"
    assert session["platform"] == "PSP"
    assert existing != conn.execute("SELECT id FROM games WHERE file_path = 'vita://UCUS98737'").fetchone()[0]


def test_vt08_the_same_title_on_another_platform_is_a_different_game(conn, tmp_path):
    upsert_game(conn, "/mnt/usb-flash/Retrogaming/PS1/Gran Turismo (USA).chd",
                display_name="Gran Turismo", canonical_name="Gran Turismo", platform="PS1")
    export(tmp_path, "UCUS98632", 100, "Gran Turismo®")           # the PSP one
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98632", 700, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    assert sessions(conn)[0]["platform"] == "PSP"


def test_vt09_an_alias_wins_over_the_title(conn, tmp_path):
    aliases = {"SCUS94455": "Gran Turismo 2"}
    export(tmp_path, "SCUS94455", 100, "GRAN TURISMO 2 - THE REAL DRIVING SIMULATOR")
    import_vita_playtime(conn, tmp_path, aliases)
    export(tmp_path, "SCUS94455", 900, "GRAN TURISMO 2 - THE REAL DRIVING SIMULATOR")
    import_vita_playtime(conn, tmp_path, aliases)
    assert sessions(conn)[0]["canonical_name"] == "Gran Turismo 2"


def test_vt11_both_discs_of_a_game_become_one_game(conn, tmp_path):
    aliases = {"SCUS94455": "Gran Turismo 2", "SCUS94488": "Gran Turismo 2"}
    for game_id in ("SCUS94455", "SCUS94488"):
        export(tmp_path, game_id, 100, "GRAN TURISMO 2")
    import_vita_playtime(conn, tmp_path, aliases)
    for game_id in ("SCUS94455", "SCUS94488"):
        export(tmp_path, game_id, 400, "GRAN TURISMO 2")
    import_vita_playtime(conn, tmp_path, aliases)
    total = conn.execute(
        "SELECT total_seconds FROM playtime_summary WHERE display_name = 'Gran Turismo 2'").fetchone()[0]
    assert total == 600


def test_vt13_broken_files_do_not_stop_the_import(conn, tmp_path):
    (tmp_path / "BAD.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "EMPTY.json").write_text("{}", encoding="utf-8")
    export(tmp_path, "UCUS98632", 100, "Gran Turismo®")
    import_vita_playtime(conn, tmp_path)
    export(tmp_path, "UCUS98632", 700, "Gran Turismo®")
    assert import_vita_playtime(conn, tmp_path) == 1


def test_vt13_missing_folder_is_nothing_to_do(conn, tmp_path):
    assert import_vita_playtime(conn, tmp_path / "does-not-exist") == 0


def test_vt15_the_folder_and_aliases_come_from_the_config(conn, tmp_path):
    from daemon.watchers.vita import import_from_config
    config = {"watchers": {"vita_playtime_dir": str(tmp_path)},
              "vita_aliases": {"SCUS94455": "Gran Turismo 2"}}
    export(tmp_path, "SCUS94455", 100, "GRAN TURISMO 2")
    import_from_config(conn, config)
    export(tmp_path, "SCUS94455", 700, "GRAN TURISMO 2")
    assert import_from_config(conn, config) == 1
    assert sessions(conn)[0]["canonical_name"] == "Gran Turismo 2"


def test_vt15_without_a_folder_in_the_config_the_watcher_is_off(conn):
    from daemon.watchers.vita import import_from_config
    assert import_from_config(conn, {"watchers": {}}) == 0
    assert import_from_config(conn, {"watchers": {"vita_playtime_dir": ""}}) == 0
