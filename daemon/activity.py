import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _to_local(started_at: str) -> datetime:
    naive = datetime.fromisoformat(started_at)
    return naive.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)


def compute_streaks(days: set[date], today: date) -> tuple[int, int]:
    if not days:
        return 0, 0

    sorted_days = sorted(days)
    longest = 1
    run = 1
    for prev, curr in zip(sorted_days, sorted_days[1:]):
        if (curr - prev).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    if today in days:
        anchor = today
    elif (today - timedelta(days=1)) in days:
        anchor = today - timedelta(days=1)
    else:
        return 0, longest

    current = 0
    d = anchor
    while d in days:
        current += 1
        d -= timedelta(days=1)

    return current, longest


HEATMAP_DAYS = 91


def compute_activity_patterns(sessions: list[dict], today: date | None = None) -> dict:
    by_weekday = [0] * 7
    by_hour = [0] * 24
    by_day: dict[date, int] = {}
    days_played: set[date] = set()
    today = today or datetime.now(LOCAL_TZ).date()

    for s in sessions:
        started_at = s.get("started_at")
        if not started_at:
            continue
        duration = s.get("duration_s") or 0
        local_dt = _to_local(started_at)
        local_date = local_dt.date()
        by_weekday[local_dt.weekday()] += duration
        by_hour[local_dt.hour] += duration
        days_played.add(local_date)
        by_day[local_date] = by_day.get(local_date, 0) + duration

    current, longest = compute_streaks(days_played, today)

    window_start = today - timedelta(days=HEATMAP_DAYS - 1)
    heatmap = [
        {
            "date": (window_start + timedelta(days=i)).isoformat(),
            "total_seconds": by_day.get(window_start + timedelta(days=i), 0),
        }
        for i in range(HEATMAP_DAYS)
    ]

    return {
        "by_weekday": [
            {"day": WEEKDAY_LABELS[i], "total_seconds": by_weekday[i]} for i in range(7)
        ],
        "by_hour": [{"hour": h, "total_seconds": by_hour[h]} for h in range(24)],
        "by_day": heatmap,
        "current_streak": current,
        "longest_streak": longest,
    }


# Mês atual + os 12 anteriores: o atual vai em destaque, os 12 fecham uma grade 6×2.
MONTHLY_WINDOW = 13
MONTHLY_TOP_GAMES = 3


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def compute_monthly(sessions: list[dict], today: date | None = None) -> list[dict]:
    """Mês atual + 12 anteriores (mais recente primeiro), com jogo do mês e totais.

    Cada sessão traz `game_key` (agrupa multi-track/multi-disco como a
    playtime_summary) e os campos exibidos do jogo. `new_games` conta jogos
    cuja primeira sessão de todo o histórico caiu naquele mês.
    """
    today = today or datetime.now(LOCAL_TZ).date()
    months = []
    y, m = today.year, today.month
    for _ in range(MONTHLY_WINDOW):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)

    first_month: dict[str, str] = {}
    buckets: dict[str, dict] = {k: {"total": 0, "count": 0, "days": set(), "games": {}} for k in months}

    for s in sessions:
        started_at = s.get("started_at")
        if not started_at:
            continue
        local_date = _to_local(started_at).date()
        key = _month_key(local_date)
        game_key = s["game_key"]
        if key < first_month.get(game_key, "9999-99"):
            first_month[game_key] = key

        bucket = buckets.get(key)
        if bucket is None:
            continue
        duration = s.get("duration_s") or 0
        bucket["total"] += duration
        bucket["count"] += 1
        bucket["days"].add(local_date)
        game = bucket["games"].setdefault(game_key, {
            "id": s["game_id"],
            "display_name": s["display_name"],
            "platform": s["platform"],
            "cover_url": s["cover_url"],
            "total_seconds": 0,
        })
        game["total_seconds"] += duration
        game["cover_url"] = game["cover_url"] or s["cover_url"]

    new_by_month: dict[str, int] = {}
    for key in first_month.values():
        new_by_month[key] = new_by_month.get(key, 0) + 1

    return [
        {
            "month": key,
            "total_seconds": buckets[key]["total"],
            "session_count": buckets[key]["count"],
            "days_played": len(buckets[key]["days"]),
            "games_played": len(buckets[key]["games"]),
            "new_games": new_by_month.get(key, 0),
            "top_games": sorted(
                buckets[key]["games"].values(), key=lambda g: g["total_seconds"], reverse=True
            )[:MONTHLY_TOP_GAMES],
        }
        for key in months
    ]


SERIES_TOP_GAMES = 10


def compute_monthly_series(sessions: list[dict], today: date | None = None) -> dict:
    """Horas por mês dos 10 jogos mais jogados de todo o histórico.

    `months` vai do mês da primeira sessão até o mês atual, sem pular meses
    vazios; cada jogo traz `monthly` com um valor por mês, na mesma ordem.
    """
    today = today or datetime.now(LOCAL_TZ).date()
    per_game: dict[str, dict] = {}
    first = _month_key(today)

    for s in sessions:
        started_at = s.get("started_at")
        if not started_at:
            continue
        key = _month_key(_to_local(started_at).date())
        first = min(first, key)
        game = per_game.setdefault(s["game_key"], {
            "id": s["game_id"],
            "display_name": s["display_name"],
            "platform": s["platform"],
            "cover_url": s["cover_url"],
            "total_seconds": 0,
            "by_month": {},
        })
        duration = s.get("duration_s") or 0
        game["total_seconds"] += duration
        game["by_month"][key] = game["by_month"].get(key, 0) + duration
        game["cover_url"] = game["cover_url"] or s["cover_url"]

    months = []
    y, m = map(int, first.split("-"))
    while (key := f"{y:04d}-{m:02d}") <= _month_key(today):
        months.append(key)
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)

    top = sorted(per_game.values(), key=lambda g: g["total_seconds"], reverse=True)[:SERIES_TOP_GAMES]
    return {
        "months": months,
        "games": [
            {
                **{k: v for k, v in g.items() if k != "by_month"},
                "monthly": [g["by_month"].get(k, 0) for k in months],
            }
            for g in top
        ],
    }


DAILY_TOP_GAMES = 10


def compute_daily_series(sessions: list[dict], today: date | None = None) -> dict:
    """Segundos por dia dos 10 jogos mais jogados no mês atual.

    `daily` vai do dia 1 até hoje (um valor por dia local); `days_in_month`
    permite desenhar o eixo do mês inteiro com os dias futuros vazios.
    """
    today = today or datetime.now(LOCAL_TZ).date()
    current = _month_key(today)
    per_game: dict[str, dict] = {}

    for s in sessions:
        started_at = s.get("started_at")
        if not started_at:
            continue
        local_date = _to_local(started_at).date()
        if _month_key(local_date) != current or local_date > today:
            continue
        game = per_game.setdefault(s["game_key"], {
            "id": s["game_id"],
            "display_name": s["display_name"],
            "platform": s["platform"],
            "cover_url": s["cover_url"],
            "total_seconds": 0,
            "daily": [0] * today.day,
        })
        duration = s.get("duration_s") or 0
        game["total_seconds"] += duration
        game["daily"][local_date.day - 1] += duration
        game["cover_url"] = game["cover_url"] or s["cover_url"]

    top = sorted(per_game.values(), key=lambda g: g["total_seconds"], reverse=True)[:DAILY_TOP_GAMES]
    return {
        "month": current,
        "days_in_month": calendar.monthrange(today.year, today.month)[1],
        "games": top,
    }
