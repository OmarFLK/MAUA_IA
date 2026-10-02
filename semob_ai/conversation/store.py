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
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, session_id)
            )"""
        )
        return connection

    def load(self, user_id: str, session_id: str) -> ConversationState:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT state_json FROM session_state WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return ConversationState(user_id=user_id, session_id=session_id)
        return ConversationState.model_validate_json(row["state_json"])

    def save(self, state: ConversationState) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """INSERT INTO session_state(user_id, session_id, state_json, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, session_id) DO UPDATE SET
                       state_json=excluded.state_json,
                       updated_at=excluded.updated_at""",
                (
                    state.user_id,
                    state.session_id,
                    state.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def clear(self, user_id: str, session_id: str) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM session_state WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
            connection.commit()
        finally:
            connection.close()

