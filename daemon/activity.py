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


def compute_activity_patterns(sessions: list[dict], today: date | None = None) -> dict:
    by_weekday = [0] * 7
    by_hour = [0] * 24
    days_played: set[date] = set()

    for s in sessions:
        started_at = s.get("started_at")
        if not started_at:
            continue
        duration = s.get("duration_s") or 0
        local_dt = _to_local(started_at)
        by_weekday[local_dt.weekday()] += duration
        by_hour[local_dt.hour] += duration
        days_played.add(local_dt.date())

    current, longest = compute_streaks(days_played, today or datetime.now(LOCAL_TZ).date())

    return {
        "by_weekday": [
            {"day": WEEKDAY_LABELS[i], "total_seconds": by_weekday[i]} for i in range(7)
        ],
        "by_hour": [{"hour": h, "total_seconds": by_hour[h]} for h in range(24)],
        "current_streak": current,
        "longest_streak": longest,
    }
