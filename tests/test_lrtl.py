import json

from daemon.watchers.lrtl import _parse_lrtl, import_sessions

_LRTL = {
    "version": "1.0",
    "runtime": "0:30:00",
    "last_played": "2026-05-23 15:00:00",
}


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


def test_import_sessions_skips_zero_runtime(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Empty.lrtl").write_text(
        json.dumps({"version": "1.0", "runtime": "0:00:00", "last_played": "2026-05-23 00:00:00"})
    )
    assert import_sessions(conn, [str(tmp_path)]) == 0
