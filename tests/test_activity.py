from datetime import date

from daemon.activity import compute_activity_patterns, compute_monthly, compute_monthly_series, compute_streaks


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


def test_compute_activity_patterns_by_day_covers_last_91_days_ending_today():
    result = compute_activity_patterns([], today=date(2026, 7, 10))

    assert len(result["by_day"]) == 91
    assert result["by_day"][0]["date"] == "2026-04-11"
    assert result["by_day"][-1]["date"] == "2026-07-10"
    assert all(d["total_seconds"] == 0 for d in result["by_day"])


def test_compute_activity_patterns_by_day_sums_sessions_on_same_local_day():
    sessions = [
        _session("2026-07-09 22:00:00", 300),  # 2026-07-09 19:00 local
        _session("2026-07-09 22:30:00", 200),  # same local day
    ]

    result = compute_activity_patterns(sessions, today=date(2026, 7, 10))

    by_day = {d["date"]: d["total_seconds"] for d in result["by_day"]}
    assert by_day["2026-07-09"] == 500


def test_compute_activity_patterns_by_day_excludes_days_outside_window():
    # More than 91 days before "today" — must not appear in by_day.
    sessions = [_session("2026-01-01 12:00:00", 500)]

    result = compute_activity_patterns(sessions, today=date(2026, 7, 10))

    assert sum(d["total_seconds"] for d in result["by_day"]) == 0


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


# --- compute_monthly ---

def _play(started_at, duration_s=600, key="mgs", name="MGS", game_id=1, cover="c.jpg", platform="PS1"):
    return {
        "started_at": started_at, "duration_s": duration_s, "game_key": key,
        "game_id": game_id, "display_name": name, "cover_url": cover, "platform": platform,
    }


def test_compute_monthly_returns_current_plus_12_months_newest_first():
    result = compute_monthly([], today=date(2026, 9, 27))

    assert [m["month"] for m in result][:3] == ["2026-09", "2026-08", "2026-07"]
    assert len(result) == 13
    assert result[-1]["month"] == "2025-09"


def test_compute_monthly_empty_month_has_zeros():
    result = compute_monthly([], today=date(2026, 9, 27))

    assert result[0] == {
        "month": "2026-09", "total_seconds": 0, "session_count": 0, "days_played": 0,
        "games_played": 0, "new_games": 0, "top_games": [],
    }


def test_compute_monthly_converts_utc_to_local_month():
    # 2026-09-01 02:00 UTC == 2026-08-31 23:00 America/Sao_Paulo → agosto
    result = compute_monthly([_play("2026-09-01 02:00:00", 900)], today=date(2026, 9, 27))

    by_month = {m["month"]: m for m in result}
    assert by_month["2026-08"]["total_seconds"] == 900
    assert by_month["2026-09"]["total_seconds"] == 0


def test_compute_monthly_ranks_top_games_by_time():
    sessions = [
        _play("2026-09-10 20:00:00", 600, key="mgs", name="MGS", game_id=1),
        _play("2026-09-11 20:00:00", 3000, key="gt4", name="GT4", game_id=2, platform="PS2"),
        _play("2026-09-12 20:00:00", 900, key="ctr", name="CTR", game_id=3),
        _play("2026-09-13 20:00:00", 300, key="dino", name="Dino", game_id=4),
        _play("2026-09-14 20:00:00", 600, key="mgs", name="MGS", game_id=1),
    ]

    month = compute_monthly(sessions, today=date(2026, 9, 27))[0]

    assert [g["display_name"] for g in month["top_games"]] == ["GT4", "MGS", "CTR"]
    assert month["top_games"][0] == {
        "id": 2, "display_name": "GT4", "platform": "PS2", "cover_url": "c.jpg", "total_seconds": 3000,
    }
    assert month["top_games"][1]["total_seconds"] == 1200
    assert month["games_played"] == 4
    assert month["session_count"] == 5
    assert month["total_seconds"] == 5400


def test_compute_monthly_counts_distinct_local_days():
    sessions = [
        _play("2026-09-10 12:00:00"),
        _play("2026-09-10 20:00:00", key="gt4"),
        _play("2026-09-11 12:00:00"),
    ]

    assert compute_monthly(sessions, today=date(2026, 9, 27))[0]["days_played"] == 2


def test_compute_monthly_new_games_uses_first_session_ever():
    # MGS estreou em agosto; em setembro só o GT4 é novo.
    sessions = [
        _play("2026-08-10 20:00:00", key="mgs"),
        _play("2026-09-10 20:00:00", key="mgs"),
        _play("2026-09-11 20:00:00", key="gt4"),
    ]

    by_month = {m["month"]: m for m in compute_monthly(sessions, today=date(2026, 9, 27))}
    assert by_month["2026-08"]["new_games"] == 1
    assert by_month["2026-09"]["new_games"] == 1


def test_compute_monthly_new_games_counts_history_before_window():
    # Estreia fora da janela não faz o jogo parecer novo dentro dela.
    sessions = [
        _play("2025-01-10 20:00:00", key="mgs"),
        _play("2026-09-10 20:00:00", key="mgs"),
    ]

    assert compute_monthly(sessions, today=date(2026, 9, 27))[0]["new_games"] == 0


# --- compute_monthly_series ---

def test_compute_monthly_series_empty_has_only_current_month():
    result = compute_monthly_series([], today=date(2026, 9, 27))

    assert result == {"months": ["2026-09"], "games": []}


def test_compute_monthly_series_spans_first_month_to_today_including_gaps():
    sessions = [_play("2026-02-10 20:00:00"), _play("2026-05-10 20:00:00")]

    result = compute_monthly_series(sessions, today=date(2026, 9, 27))

    assert result["months"] == ["2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


def test_compute_monthly_series_spans_year_boundary():
    result = compute_monthly_series([_play("2025-11-10 20:00:00")], today=date(2026, 1, 5))

    assert result["months"] == ["2025-11", "2025-12", "2026-01"]


def test_compute_monthly_series_game_has_one_value_per_month_in_local_time():
    # 2026-08-01 02:00 UTC == 2026-07-31 23:00 America/Sao_Paulo → julho
    sessions = [
        _play("2026-07-10 20:00:00", 600),
        _play("2026-08-01 02:00:00", 300),
        _play("2026-09-10 20:00:00", 900),
    ]

    game = compute_monthly_series(sessions, today=date(2026, 9, 27))["games"][0]

    assert game["monthly"] == [900, 0, 900]
    assert game["total_seconds"] == 1800
    assert game == {**game, "id": 1, "display_name": "MGS", "platform": "PS1", "cover_url": "c.jpg"}


def test_compute_monthly_series_keeps_top_10_by_total_time():
    sessions = [
        _play("2026-09-10 20:00:00", 1000 + i, key=f"g{i}", name=f"G{i}", game_id=i)
        for i in range(12)
    ]

    games = compute_monthly_series(sessions, today=date(2026, 9, 27))["games"]

    assert len(games) == 10
    assert [g["display_name"] for g in games[:2]] == ["G11", "G10"]
    assert "G0" not in [g["display_name"] for g in games]
