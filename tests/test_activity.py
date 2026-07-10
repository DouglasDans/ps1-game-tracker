from datetime import date

from daemon.activity import compute_activity_patterns, compute_streaks


def _session(started_at, duration_s=600):
    return {"started_at": started_at, "duration_s": duration_s}


# --- compute_activity_patterns ---

def test_compute_activity_patterns_empty():
    result = compute_activity_patterns([])

    assert len(result["by_weekday"]) == 7
    assert all(d["total_seconds"] == 0 for d in result["by_weekday"])
    assert len(result["by_hour"]) == 24
    assert all(h["total_seconds"] == 0 for h in result["by_hour"])
    assert result["current_streak"] == 0
    assert result["longest_streak"] == 0


def test_compute_activity_patterns_converts_utc_to_local_weekday_and_hour():
    # 2026-07-10 02:30:00 UTC == 2026-07-09 23:30:00 America/Sao_Paulo (UTC-3)
    # 2026-07-09 is a Thursday
    sessions = [_session("2026-07-10 02:30:00", duration_s=900)]

    result = compute_activity_patterns(sessions, today=date(2026, 7, 10))

    by_weekday = {d["day"]: d["total_seconds"] for d in result["by_weekday"]}
    by_hour = {h["hour"]: h["total_seconds"] for h in result["by_hour"]}
    assert by_weekday["Qui"] == 900
    assert by_hour[23] == 900


def test_compute_activity_patterns_sums_multiple_sessions_same_bucket():
    sessions = [
        _session("2026-07-09 22:00:00", 300),  # 19:00 local
        _session("2026-07-09 22:30:00", 200),  # 19:30 local, same hour bucket
    ]

    result = compute_activity_patterns(sessions, today=date(2026, 7, 10))

    by_hour = {h["hour"]: h["total_seconds"] for h in result["by_hour"]}
    assert by_hour[19] == 500


def test_compute_activity_patterns_ignores_none_duration():
    sessions = [_session("2026-07-09 22:00:00", duration_s=None)]

    result = compute_activity_patterns(sessions, today=date(2026, 7, 10))

    assert sum(h["total_seconds"] for h in result["by_hour"]) == 0


def test_compute_activity_patterns_skips_sessions_without_started_at():
    sessions = [{"started_at": None, "duration_s": 100}]

    result = compute_activity_patterns(sessions, today=date(2026, 7, 10))

    assert sum(h["total_seconds"] for h in result["by_hour"]) == 0


# --- compute_streaks ---

def test_compute_streaks_empty():
    assert compute_streaks(set(), date(2026, 7, 10)) == (0, 0)


def test_compute_streaks_today_only():
    days = {date(2026, 7, 10)}
    assert compute_streaks(days, date(2026, 7, 10)) == (1, 1)


def test_compute_streaks_consecutive_ending_today():
    days = {date(2026, 7, 8), date(2026, 7, 9), date(2026, 7, 10)}
    assert compute_streaks(days, date(2026, 7, 10)) == (3, 3)


def test_compute_streaks_ongoing_streak_not_yet_played_today():
    # last play was yesterday — streak should not reset just because
    # today hasn't happened yet
    days = {date(2026, 7, 7), date(2026, 7, 8), date(2026, 7, 9)}

    current, longest = compute_streaks(days, date(2026, 7, 10))

    assert current == 3
    assert longest == 3


def test_compute_streaks_broken_streak_resets_current_to_zero():
    days = {date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)}

    current, longest = compute_streaks(days, date(2026, 7, 10))

    assert current == 0
    assert longest == 3


def test_compute_streaks_longest_can_differ_from_current():
    days = {
        date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3),
        date(2026, 6, 4), date(2026, 6, 5),
        date(2026, 7, 9), date(2026, 7, 10),
    }

    current, longest = compute_streaks(days, date(2026, 7, 10))

    assert current == 2
    assert longest == 5
