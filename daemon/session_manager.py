import logging
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from daemon.db import close_session, heartbeat, open_session, resume_session, upsert_game

_TRAILING_PARENS_RE = re.compile(r"\s*\([^)]*\)\s*$")
_TRAILING_BRACKETS_RE = re.compile(r"\s*\[[^\]]*\]\s*$")
_TRAILING_VERSION_RE = re.compile(r"\s+v\d+\S*$")  # strips " v1.001", " v2.0", etc.
_PS2_SERIAL_RE = re.compile(r"^[A-Z]{4}_\d{3}\.\d{2}\.(.+)$")


def normalize_game_name(stem: str) -> str:
    result = stem
    while True:
        stripped = _TRAILING_PARENS_RE.sub("", result).strip()
        stripped = _TRAILING_BRACKETS_RE.sub("", stripped).strip()
        stripped = _TRAILING_VERSION_RE.sub("", stripped).strip()
        if stripped == result:
            return result
        result = stripped


def strip_ps2_serial(stem: str) -> str:
    m = _PS2_SERIAL_RE.match(stem)
    return m.group(1) if m else stem

logger = logging.getLogger(__name__)

_PATH_PLATFORMS: dict[str, str] = {
    "PS1":   "PS1",
    "PSX":   "PS1",
    "PSP":   "PSP",
    "PS2":   "PS2",
    "PS2SMB": "PS2",
}

_SOURCE_PLATFORMS: dict[str, str] = {
    "duckstation": "PS1",
    "ppsspp":      "PSP",
    "samba":       "PS2",
}


def infer_metadata(file_path: str, source: str) -> tuple[str, str | None]:
    display_name = normalize_game_name(strip_ps2_serial(Path(file_path).stem))
    parts = Path(file_path).parts
    for part in parts:
        platform = _PATH_PLATFORMS.get(part.upper())
        if platform:
            return display_name, platform
    return display_name, _SOURCE_PLATFORMS.get(source)


@dataclass
class SessionManager:
    conn: sqlite3.Connection
    resume_grace_s: float = 35.0
    now_fn: Callable[[], float] = field(default=time.monotonic)
    _active_session_id: int | None = field(default=None, init=False)
    _active_file_path: str | None = field(default=None, init=False)
    _active_canonical_name: str | None = field(default=None, init=False)
    _active_source: str | None = field(default=None, init=False)
    _last_closed_session_id: int | None = field(default=None, init=False)
    _last_closed_canonical_name: str | None = field(default=None, init=False)
    _last_closed_source: str | None = field(default=None, init=False)
    _last_closed_at: float | None = field(default=None, init=False)

    def on_game_start(self, file_path: str, source: str) -> None:
        display_name, platform = infer_metadata(file_path, source)
        canonical_name = display_name

        if self._active_canonical_name == canonical_name:
            return

        if self._active_session_id is not None:
            self._close_current()

        if self._can_resume(canonical_name, source):
            resume_session(self.conn, self._last_closed_session_id)
            self._active_session_id = self._last_closed_session_id
            self._active_file_path = file_path
            self._active_canonical_name = canonical_name
            self._active_source = source
            self._last_closed_session_id = None
            logger.info("Session resumed: %s (%s)", file_path, source)
            return

        game_id = upsert_game(self.conn, file_path, display_name, platform, canonical_name)
        self._active_session_id = open_session(self.conn, game_id, source)
        self._active_file_path = file_path
        self._active_canonical_name = canonical_name
        self._active_source = source
        logger.info("Session opened: %s (%s)", file_path, source)

    def on_game_stop(self) -> None:
        if self._active_session_id is None:
            return
        self._close_current()

    def send_heartbeat(self) -> None:
        if self._active_session_id is not None:
            heartbeat(self.conn, self._active_session_id)

    def _can_resume(self, canonical_name: str, source: str) -> bool:
        return (
            self._last_closed_session_id is not None
            and self._last_closed_canonical_name == canonical_name
            and self._last_closed_source == source
            and (self.now_fn() - self._last_closed_at) <= self.resume_grace_s
        )

    def _close_current(self) -> None:
        close_session(self.conn, self._active_session_id)
        logger.info("Session closed: %s", self._active_file_path)
        self._last_closed_session_id = self._active_session_id
        self._last_closed_canonical_name = self._active_canonical_name
        self._last_closed_source = self._active_source
        self._last_closed_at = self.now_fn()
        self._active_session_id = None
        self._active_file_path = None
        self._active_canonical_name = None
        self._active_source = None
