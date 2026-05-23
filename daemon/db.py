import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            id                    INTEGER PRIMARY KEY,
            file_path             TEXT UNIQUE NOT NULL,
            file_md5              TEXT,
            display_name          TEXT,
            platform              TEXT,
            cover_url             TEXT,
            genre                 TEXT,
            release_year          INTEGER,
            enriched_at           DATETIME,
            notion_page_id        TEXT,
            ra_game_id            INTEGER,
            ra_points_possible    INTEGER,
            ra_achievements_count INTEGER
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
    try:
        conn.execute("ALTER TABLE games ADD COLUMN canonical_name TEXT")
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
            MAX(s.started_at)                                                  AS last_played
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


def get_games(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, file_path, display_name, platform, cover_url, "
        "session_count, total_seconds, last_played FROM playtime_summary"
    ).fetchall()
    return [dict(r) for r in rows]
