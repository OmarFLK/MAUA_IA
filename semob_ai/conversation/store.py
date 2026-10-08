from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from semob_ai.conversation.models import ConversationState


class SessionStore:
    """Persistent working state keyed by both user and session."""

    def __init__(self, database_file: Path):
        self.database_file = database_file

    def _connect(self) -> sqlite3.Connection:
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS session_state (
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                assistant_mode TEXT NOT NULL DEFAULT 'cmob',
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, session_id)
            )"""
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(session_state)")}
        if "assistant_mode" not in columns:
            connection.execute(
                "ALTER TABLE session_state ADD COLUMN assistant_mode TEXT NOT NULL DEFAULT 'cmob'"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_session_mode ON session_state(user_id, assistant_mode, updated_at)"
        )
        connection.commit()
        return connection

    def load(self, user_id: str, session_id: str, assistant_mode: str = "cmob") -> ConversationState:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT state_json FROM session_state WHERE user_id = ? AND session_id = ? AND assistant_mode = ?",
                (user_id, session_id, assistant_mode),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return ConversationState(user_id=user_id, session_id=session_id)
        return ConversationState.model_validate_json(row["state_json"])

    def save(self, state: ConversationState, assistant_mode: str = "cmob") -> None:
        connection = self._connect()
        try:
            connection.execute(
                """INSERT INTO session_state(user_id, session_id, assistant_mode, state_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, session_id) DO UPDATE SET
                       assistant_mode=excluded.assistant_mode,
                       state_json=excluded.state_json,
                       updated_at=excluded.updated_at""",
                (
                    state.user_id,
                    state.session_id,
                    assistant_mode,
                    state.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def clear(self, user_id: str, session_id: str, assistant_mode: str = "cmob") -> None:
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM session_state WHERE user_id = ? AND session_id = ? AND assistant_mode = ?",
                (user_id, session_id, assistant_mode),
            )
            connection.commit()
        finally:
            connection.close()

