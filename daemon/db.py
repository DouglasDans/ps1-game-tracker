import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            id               INTEGER PRIMARY KEY,
            file_path        TEXT UNIQUE NOT NULL,
            file_md5         TEXT,
            display_name     TEXT,
            platform         TEXT,
            cover_url        TEXT,
            genre            TEXT,
            release_year     INTEGER,
            enriched_at      DATETIME,
            notion_page_id   TEXT,
            igdb_id          INTEGER,
            screenscraper_id INTEGER,
            ra_game_id       INTEGER
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id               INTEGER PRIMARY KEY,
            game_id          INTEGER NOT NULL REFERENCES games(id),
            source           TEXT NOT NULL,
            started_at       DATETIME NOT NULL DEFAULT (datetime('now')),
            ended_at         DATETIME,
            heartbeat_at     DATETIME,
            duration_s       INTEGER,
            ended_abnormally INTEGER DEFAULT 0,
            synced_to_notion INTEGER DEFAULT 0
        );
    """)
    for col, typedef in [
        ("canonical_name", "TEXT"),
        ("igdb_id", "INTEGER"),
        ("screenscraper_id", "INTEGER"),
        ("enrichment_retries", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass
    conn.executescript("""
        DROP VIEW IF EXISTS playtime_summary;
        CREATE VIEW playtime_summary AS
        SELECT
            MIN(g.id)                                                          AS id,
            MIN(g.file_path)                                                   AS file_path,
            COALESCE(g.canonical_name, COALESCE(g.display_name, g.file_path)) AS display_name,
            MIN(g.platform)                                                    AS platform,
            MIN(g.cover_url)                                                   AS cover_url,
            COUNT(s.id)                                                        AS session_count,
            SUM(s.duration_s)                                                  AS total_seconds,
            MAX(s.started_at)                                                  AS last_played,
            (
                SELECT s2.source
                FROM sessions s2
                JOIN games g2 ON g2.id = s2.game_id
                WHERE COALESCE(g2.canonical_name, g2.file_path) = COALESCE(g.canonical_name, g.file_path)
                  AND s2.ended_at IS NOT NULL
                ORDER BY s2.started_at DESC
                LIMIT 1
            )                                                                  AS last_source
        FROM games g
        JOIN sessions s ON s.game_id = g.id
        WHERE s.ended_at IS NOT NULL
        GROUP BY COALESCE(g.canonical_name, g.file_path)
        ORDER BY total_seconds DESC;
    """)
    conn.commit()


def upsert_game(
    conn: sqlite3.Connection,
    file_path: str,
    display_name: str | None = None,
    platform: str | None = None,
    canonical_name: str | None = None,
) -> int:
    conn.execute(
        """
        INSERT INTO games (file_path, display_name, platform, canonical_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            display_name   = COALESCE(games.display_name,   excluded.display_name),
            platform       = COALESCE(games.platform,       excluded.platform),
            canonical_name = COALESCE(games.canonical_name, excluded.canonical_name)
        """,
        (file_path, display_name, platform, canonical_name),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM games WHERE file_path = ?", (file_path,)).fetchone()
    return row[0]


def open_session(conn: sqlite3.Connection, game_id: int, source: str) -> int:
    cursor = conn.execute(
        "INSERT INTO sessions (game_id, source, started_at, heartbeat_at) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        (game_id, source),
    )
    conn.commit()
    return cursor.lastrowid


def close_session(conn: sqlite3.Connection, session_id: int, abnormal: bool = False) -> None:
    conn.execute(
        """
        UPDATE sessions
        SET ended_at         = datetime('now'),
            heartbeat_at     = datetime('now'),
            duration_s       = CAST(
                (julianday('now') - julianday(started_at)) * 86400 AS INTEGER
            ),
            ended_abnormally = ?
        WHERE id = ?
        """,
        (1 if abnormal else 0, session_id),
    )
    conn.commit()


def heartbeat(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute(
        "UPDATE sessions SET heartbeat_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def crash_recovery(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        """
        UPDATE sessions
        SET ended_at         = COALESCE(heartbeat_at, started_at),
            duration_s       = CAST(
                (julianday(COALESCE(heartbeat_at, started_at)) - julianday(started_at)) * 86400
                AS INTEGER
            ),
            ended_abnormally = 1
        WHERE ended_at IS NULL
          AND (heartbeat_at IS NULL OR heartbeat_at < datetime('now', '-5 minutes'))
        """
    )
    conn.commit()
    return cursor.rowcount


def get_active_session(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        """
        SELECT s.id, s.game_id, s.source, s.started_at,
               g.file_path,
               COALESCE(g.display_name, g.file_path) AS display_name
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NULL
        ORDER BY s.started_at DESC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def reset_all_enrichment(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        """
        UPDATE games SET
            enriched_at        = NULL,
            enrichment_retries = 0,
            cover_url          = NULL,
            igdb_id            = NULL,
            screenscraper_id   = NULL,
            display_name       = COALESCE(canonical_name, display_name)
        WHERE enriched_at IS NOT NULL OR enrichment_retries > 0
        """
    )
    conn.commit()
    return cursor.rowcount


def get_unenriched_games(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, file_path, display_name, platform, canonical_name "
        "FROM games WHERE enriched_at IS NULL AND enrichment_retries < 3"
    ).fetchall()
    return [dict(r) for r in rows]


def update_game_enrichment(
    conn: sqlite3.Connection,
    game_id: int,
    *,
    display_name: str | None = None,
    cover_url: str | None = None,
    genre: str | None = None,
    release_year: int | None = None,
    igdb_id: int | None = None,
    screenscraper_id: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE games SET
            display_name     = COALESCE(?, display_name),
            cover_url        = COALESCE(?, cover_url),
            genre            = COALESCE(?, genre),
            release_year     = COALESCE(?, release_year),
            igdb_id          = COALESCE(?, igdb_id),
            screenscraper_id = COALESCE(?, screenscraper_id),
            enriched_at      = datetime('now')
        WHERE id = ?
        """,
        (display_name, cover_url, genre, release_year, igdb_id, screenscraper_id, game_id),
    )
    conn.commit()


def increment_enrichment_retries(conn: sqlite3.Connection, game_id: int) -> None:
    conn.execute(
        "UPDATE games SET enrichment_retries = enrichment_retries + 1 WHERE id = ?",
        (game_id,),
    )
    conn.commit()


def get_game_detail(conn: sqlite3.Connection, game_id: int) -> dict | None:
    game = conn.execute(
        "SELECT id, file_path, display_name, platform, cover_url, genre, release_year, igdb_id, canonical_name "
        "FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()
    if not game:
        return None

    group_key = game["canonical_name"] or game["file_path"]

    summary = conn.execute(
        """
        SELECT COUNT(s.id) AS session_count,
               COALESCE(SUM(s.duration_s), 0) AS total_seconds,
               MAX(s.started_at) AS last_played,
               MIN(s.started_at) AS first_played,
               CASE WHEN COUNT(s.id) > 0 THEN AVG(s.duration_s) ELSE NULL END AS avg_session_s,
               MAX(s.duration_s) AS longest_session_s
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL
          AND COALESCE(g.canonical_name, g.file_path) = ?
        """,
        (group_key,),
    ).fetchone()

    longest_row = conn.execute(
        """
        SELECT DATE(s.started_at) AS day
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL
          AND s.duration_s IS NOT NULL
          AND COALESCE(g.canonical_name, g.file_path) = ?
        ORDER BY s.duration_s DESC
        LIMIT 1
        """,
        (group_key,),
    ).fetchone()

    best_day_row = conn.execute(
        """
        SELECT DATE(s.started_at) AS day, SUM(s.duration_s) AS total
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL
          AND COALESCE(g.canonical_name, g.file_path) = ?
        GROUP BY DATE(s.started_at)
        ORDER BY total DESC
        LIMIT 1
        """,
        (group_key,),
    ).fetchone()

    sessions = conn.execute(
        """
        SELECT s.id, s.started_at, s.ended_at, s.duration_s, s.source
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL
          AND COALESCE(g.canonical_name, g.file_path) = ?
        ORDER BY s.started_at DESC
        """,
        (group_key,),
    ).fetchall()

    return {
        "id": game_id,
        "display_name": game["display_name"],
        "platform": game["platform"],
        "cover_url": game["cover_url"],
        "genre": game["genre"],
        "release_year": game["release_year"],
        "igdb_id": game["igdb_id"],
        "total_seconds": summary["total_seconds"],
        "session_count": summary["session_count"],
        "last_played": summary["last_played"],
        "first_played": summary["first_played"],
        "avg_session_s": summary["avg_session_s"],
        "longest_session_s": summary["longest_session_s"],
        "longest_session_date": longest_row["day"] if longest_row else None,
        "best_day": best_day_row["day"] if best_day_row else None,
        "best_day_total_s": best_day_row["total"] if best_day_row else None,
        "sessions": [dict(s) for s in sessions],
    }


def get_stats_summary(conn: sqlite3.Connection) -> dict:
    totals = conn.execute(
        """
        SELECT COALESCE(SUM(s.duration_s), 0) AS total_seconds,
               COUNT(DISTINCT COALESCE(g.canonical_name, g.file_path)) AS total_games
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL
        """,
    ).fetchone()

    most_played = conn.execute(
        "SELECT id, display_name, total_seconds FROM playtime_summary LIMIT 1"
    ).fetchone()

    longest = conn.execute(
        """
        SELECT s.duration_s, s.started_at,
               COALESCE(g.canonical_name, g.display_name, g.file_path) AS display_name
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL AND s.duration_s IS NOT NULL
        ORDER BY s.duration_s DESC
        LIMIT 1
        """,
    ).fetchone()

    total_secs = totals["total_seconds"]

    by_platform = conn.execute(
        """
        WITH resolved AS (
            SELECT s.duration_s,
                   COALESCE(
                       g.platform,
                       (SELECT g2.platform FROM games g2
                        WHERE g2.canonical_name = g.canonical_name
                          AND g2.platform IS NOT NULL
                        LIMIT 1),
                       'Outros'
                   ) AS platform
            FROM sessions s
            JOIN games g ON g.id = s.game_id
            WHERE s.ended_at IS NOT NULL
        )
        SELECT platform, COALESCE(SUM(duration_s), 0) AS total_seconds
        FROM resolved
        GROUP BY platform
        ORDER BY total_seconds DESC
        """,
    ).fetchall()

    return {
        "total_seconds": total_secs,
        "total_games": totals["total_games"],
        "most_played": dict(most_played) if most_played else None,
        "longest_session": dict(longest) if longest else None,
        "by_platform": [
            {
                "platform": row["platform"],
                "total_seconds": row["total_seconds"],
                "pct": round(row["total_seconds"] * 100 / total_secs) if total_secs > 0 else 0,
            }
            for row in by_platform
        ],
    }


def get_recent_sessions(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.id, s.game_id,
               COALESCE(g.display_name, g.file_path) AS display_name,
               g.platform, g.cover_url, s.source,
               s.started_at, s.ended_at, s.duration_s
        FROM sessions s
        JOIN games g ON g.id = s.game_id
        WHERE s.ended_at IS NOT NULL
        ORDER BY s.started_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_games(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, file_path, display_name, platform, cover_url, "
        "session_count, total_seconds, last_played, last_source FROM playtime_summary"
    ).fetchall()
    return [dict(r) for r in rows]
