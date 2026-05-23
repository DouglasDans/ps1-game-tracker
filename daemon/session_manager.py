import logging
import sqlite3
from dataclasses import dataclass, field

from daemon.db import close_session, heartbeat, open_session, upsert_game

logger = logging.getLogger(__name__)


@dataclass
class SessionManager:
    conn: sqlite3.Connection
    _active_session_id: int | None = field(default=None, init=False)
    _active_file_path: str | None = field(default=None, init=False)

    def on_game_start(self, file_path: str, source: str) -> None:
        if self._active_file_path == file_path:
            return

        if self._active_session_id is not None:
            self._close_current()

        game_id = upsert_game(self.conn, file_path)
        self._active_session_id = open_session(self.conn, game_id, source)
        self._active_file_path = file_path
        logger.info("Session opened: %s (%s)", file_path, source)

    def on_game_stop(self) -> None:
        if self._active_session_id is None:
            return
        self._close_current()

    def send_heartbeat(self) -> None:
        if self._active_session_id is not None:
            heartbeat(self.conn, self._active_session_id)

    def _close_current(self) -> None:
        close_session(self.conn, self._active_session_id)
        logger.info("Session closed: %s", self._active_file_path)
        self._active_session_id = None
        self._active_file_path = None
