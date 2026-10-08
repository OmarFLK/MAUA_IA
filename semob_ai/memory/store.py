from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class MemoryTurn:
    role: str
    content: str
    created_at: str


class MemoryStore:
    def __init__(self, database_file: Path, retention_days: int = 30):
        self.database_file = database_file
        self.retention_days = retention_days

    def _connect(self) -> sqlite3.Connection:
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                assistant_mode TEXT NOT NULL DEFAULT 'cmob',
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )"""
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(conversation_turns)")}
        if "assistant_mode" not in columns:
            connection.execute(
                "ALTER TABLE conversation_turns ADD COLUMN assistant_mode TEXT NOT NULL DEFAULT 'cmob'"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_turn_owner_mode ON conversation_turns(user_id, assistant_mode, conversation_id, created_at)"
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, key)
            )"""
        )
        connection.commit()
        return connection

    def add_turn(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        assistant_mode: str = "cmob",
    ) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Papel de memória inválido.")
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.retention_days)
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO conversation_turns(user_id, conversation_id, assistant_mode, role, content, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, conversation_id, assistant_mode, role, content, now.isoformat(), expires.isoformat()),
            )
            connection.commit()
        finally:
            connection.close()

    def recent(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 12,
        assistant_mode: str = "cmob",
    ) -> list[MemoryTurn]:
        connection = self._connect()
        try:
            rows = connection.execute(
                """SELECT role, content, created_at FROM conversation_turns
                   WHERE user_id = ? AND conversation_id = ? AND assistant_mode = ? AND expires_at > ?
                   ORDER BY created_at DESC LIMIT ?""",
                (
                    user_id,
                    conversation_id,
                    assistant_mode,
                    datetime.now(timezone.utc).isoformat(),
                    min(limit, 50),
                ),
            ).fetchall()
        finally:
            connection.close()
        return [MemoryTurn(row["role"], row["content"], row["created_at"]) for row in reversed(rows)]

    def set_preference(self, user_id: str, key: str, value: str) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """INSERT INTO preferences(user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (user_id, key, value, datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
        finally:
            connection.close()

    def preferences(self, user_id: str) -> dict[str, str]:
        connection = self._connect()
        try:
            rows = connection.execute("SELECT key, value FROM preferences WHERE user_id = ?", (user_id,)).fetchall()
        finally:
            connection.close()
        return {row["key"]: row["value"] for row in rows}

    def purge_expired(self) -> int:
        connection = self._connect()
        try:
            cursor = connection.execute(
                "DELETE FROM conversation_turns WHERE expires_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()

