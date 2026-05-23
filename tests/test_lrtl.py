import json

import pytest

from daemon.watchers.lrtl import _parse_lrtl, import_sessions

_LRTL_DICT = {
    "version": "1.0",
    "runtime_log": {
        "runtime_hours": 0,
        "runtime_minutes": 30,
        "runtime_seconds": 0,
        "last_played_year": 2026,
        "last_played_month": 5,
        "last_played_day": 23,
        "last_played_hour": 15,
        "last_played_minute": 0,
        "last_played_second": 0,
    },
}

_LRTL_LIST = {
    "version": "1.0",
    "runtime_log": [_LRTL_DICT["runtime_log"]],
}


def test_parse_lrtl_dict_format():
    result = _parse_lrtl(_LRTL_DICT)
    assert result is not None
    runtime_s, last_played = result
    assert runtime_s == 1800
    assert last_played.year == 2026
    assert last_played.hour == 15


def test_parse_lrtl_list_format():
    result = _parse_lrtl(_LRTL_LIST)
    assert result is not None
    runtime_s, _ = result
    assert runtime_s == 1800


def test_parse_lrtl_returns_none_for_empty_dict():
    assert _parse_lrtl({}) is None


def test_parse_lrtl_returns_none_for_missing_date_fields():
    assert _parse_lrtl({"runtime_log": {}}) is None


def test_parse_lrtl_returns_zero_runtime_when_all_zeros():
    data = {
        "runtime_log": {
            "runtime_hours": 0,
            "runtime_minutes": 0,
            "runtime_seconds": 0,
            "last_played_year": 2026,
            "last_played_month": 5,
            "last_played_day": 23,
            "last_played_hour": 0,
            "last_played_minute": 0,
            "last_played_second": 0,
        }
    }
    result = _parse_lrtl(data)
    assert result is not None
    runtime_s, _ = result
    assert runtime_s == 0


def test_import_sessions_creates_session_for_new_content(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL_DICT))

    n = import_sessions(conn, [str(tmp_path)])

    assert n == 1
    row = conn.execute(
        "SELECT duration_s, source FROM sessions WHERE source = 'retroarch'"
    ).fetchone()
    assert row is not None
    assert row["duration_s"] == 1800
    assert row["source"] == "retroarch"


def test_import_sessions_skips_already_imported(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Ico.lrtl").write_text(json.dumps(_LRTL_DICT))

    import_sessions(conn, [str(tmp_path)])
    n = import_sessions(conn, [str(tmp_path)])

    assert n == 0
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_import_sessions_skips_nonexistent_dir(conn):
    n = import_sessions(conn, ["/nonexistent/path"])
    assert n == 0


def test_import_sessions_handles_corrupt_lrtl(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "Broken.lrtl").write_text("not valid json {{{")

    n = import_sessions(conn, [str(tmp_path)])
    assert n == 0


def test_import_sessions_skips_zero_runtime(conn, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    zero_runtime = {
        "runtime_log": {
            "runtime_hours": 0,
            "runtime_minutes": 0,
            "runtime_seconds": 0,
            "last_played_year": 2026,
            "last_played_month": 5,
            "last_played_day": 23,
            "last_played_hour": 0,
            "last_played_minute": 0,
            "last_played_second": 0,
        }
    }
    (logs_dir / "Empty.lrtl").write_text(json.dumps(zero_runtime))

    n = import_sessions(conn, [str(tmp_path)])
    assert n == 0
