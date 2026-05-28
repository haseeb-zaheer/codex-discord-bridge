from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Session:
    id: str
    alias: str
    user_id: int
    channel_id: int
    cwd: str
    model: str | None
    status: str
    created_at: float
    updated_at: float
    last_prompt: str | None
    last_error: str | None
    log_path: str | None


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    alias TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    cwd TEXT NOT NULL,
                    model TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_prompt TEXT,
                    last_error TEXT,
                    log_path TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_sessions (
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    PRIMARY KEY (user_id, channel_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")

    def upsert_session(
        self,
        *,
        session_id: str,
        alias: str,
        user_id: int,
        channel_id: int,
        cwd: Path,
        model: str | None,
        status: str = "idle",
        last_prompt: str | None = None,
        last_error: str | None = None,
        log_path: Path | None = None,
    ) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, alias, user_id, channel_id, cwd, model, status, created_at, updated_at,
                    last_prompt, last_error, log_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    alias=excluded.alias,
                    cwd=excluded.cwd,
                    model=excluded.model,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    last_prompt=excluded.last_prompt,
                    last_error=excluded.last_error,
                    log_path=excluded.log_path
                """,
                (
                    session_id,
                    alias,
                    user_id,
                    channel_id,
                    str(cwd),
                    model,
                    status,
                    now,
                    now,
                    last_prompt,
                    last_error,
                    str(log_path) if log_path else None,
                ),
            )

    def set_active(self, user_id: int, channel_id: int, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO active_sessions (user_id, channel_id, session_id)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, channel_id) DO UPDATE SET session_id=excluded.session_id
                """,
                (user_id, channel_id, session_id),
            )

    def get_active(self, user_id: int, channel_id: int) -> Session | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.* FROM sessions s
                JOIN active_sessions a ON a.session_id = s.id
                WHERE a.user_id = ? AND a.channel_id = ?
                """,
                (user_id, channel_id),
            ).fetchone()
        return _row_to_session(row)

    def find_session(self, user_id: int, identifier: str) -> Session | None:
        pattern = f"{identifier}%"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sessions
                WHERE user_id = ? AND (id = ? OR alias = ? OR id LIKE ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id, identifier, identifier, pattern),
            ).fetchone()
        return _row_to_session(row)

    def list_sessions(self, user_id: int, limit: int = 10) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [_row_to_session(row) for row in rows if row is not None]

    def set_status(self, session_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error, time.time(), session_id),
            )

    def set_model(self, session_id: str, model: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET model = ?, updated_at = ? WHERE id = ?",
                (model, time.time(), session_id),
            )


def _row_to_session(row: sqlite3.Row | None) -> Session | None:
    if row is None:
        return None
    return Session(
        id=row["id"],
        alias=row["alias"],
        user_id=row["user_id"],
        channel_id=row["channel_id"],
        cwd=row["cwd"],
        model=row["model"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_prompt=row["last_prompt"],
        last_error=row["last_error"],
        log_path=row["log_path"],
    )
