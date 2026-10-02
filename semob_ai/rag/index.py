from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np


TOKEN_PATTERN = re.compile(r"[\wÀ-ÿ]{2,}", re.UNICODE)
VECTOR_SIZE = 384


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    chunk_index: int
    text: str
    score: float


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def _embedding(text: str) -> np.ndarray:
    vector = np.zeros(VECTOR_SIZE, dtype=np.float32)
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % VECTOR_SIZE
        vector[index] += -1.0 if digest[4] & 1 else 1.0
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _chunks(text: str, size: int = 180, overlap: int = 30) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]


class LocalRagIndex:
    def __init__(self, database_file: Path):
        self.database_file = database_file

    def _connect(self) -> sqlite3.Connection:
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_file)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                embedding BLOB NOT NULL,
                UNIQUE(source, chunk_index)
            )"""
        )
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(content, tokenize='unicode61 remove_diacritics 2')"
        )
        return connection

    def rebuild(self, document_root: Path) -> int:
        document_root = document_root.resolve()
        files = sorted(path for path in document_root.rglob("*") if path.is_file() and path.suffix.casefold() in {".md", ".txt"})
        connection = self._connect()
        count = 0
        try:
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM chunks_fts")
            for path in files:
                text = path.read_text(encoding="utf-8", errors="replace")
                source = path.relative_to(document_root).as_posix()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                for index, content in enumerate(_chunks(text)):
                    cursor = connection.execute(
                        "INSERT INTO chunks(source, chunk_index, content, sha256, embedding) VALUES (?, ?, ?, ?, ?)",
                        (source, index, content, digest, _embedding(content).tobytes()),
                    )
                    connection.execute("INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)", (cursor.lastrowid, content))
                    count += 1
            connection.commit()
        finally:
            connection.close()
        return count

    def search(self, query: str, limit: int = 5) -> list[RetrievedChunk]:
        query_tokens = list(dict.fromkeys(_tokens(query)))[:12]
        if not query_tokens or not self.database_file.is_file():
            return []
        connection = self._connect()
        try:
            lexical_rows = connection.execute(
                "SELECT rowid, bm25(chunks_fts) FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
                (" OR ".join(f'"{token}"' for token in query_tokens), limit * 4),
            ).fetchall()
            lexical = {row_id: 1.0 / (1.0 + abs(score)) for row_id, score in lexical_rows}
            query_vector = _embedding(query)
            candidates = connection.execute("SELECT id, source, chunk_index, content, embedding FROM chunks").fetchall()
        finally:
            connection.close()

        ranked: list[RetrievedChunk] = []
        for row_id, source, chunk_index, content, blob in candidates:
            semantic = float(np.dot(query_vector, np.frombuffer(blob, dtype=np.float32)))
            score = 0.65 * lexical.get(row_id, 0.0) + 0.35 * max(semantic, 0.0)
            if score > 0:
                ranked.append(RetrievedChunk(source, chunk_index, content, score))
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:limit]

