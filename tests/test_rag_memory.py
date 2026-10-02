from __future__ import annotations

from pathlib import Path

from semob_ai.memory import MemoryStore
from semob_ai.rag import LocalRagIndex


def test_local_rag_indexes_text_with_provenance(tmp_path: Path) -> None:
    documents = tmp_path / "docs"
    documents.mkdir()
    (documents / "operacao.md").write_text(
        "A quilometragem improdutiva representa o deslocamento operacional sem passageiros.",
        encoding="utf-8",
    )
    index = LocalRagIndex(tmp_path / "rag.sqlite")

    assert index.rebuild(documents) == 1
    results = index.search("O que significa quilometragem improdutiva?")

    assert results
    assert results[0].source == "operacao.md"
    assert "sem passageiros" in results[0].text


def test_memory_is_isolated_by_user_and_conversation(tmp_path: Path) -> None:
    memory = MemoryStore(tmp_path / "memory.sqlite")
    memory.add_turn("user-a", "chat-1", "user", "Analise a linha 101")
    memory.add_turn("user-b", "chat-1", "user", "Analise a linha 202")
    memory.set_preference("user-a", "formato", "tabela")

    turns = memory.recent("user-a", "chat-1")

    assert [turn.content for turn in turns] == ["Analise a linha 101"]
    assert memory.preferences("user-a") == {"formato": "tabela"}
    assert memory.preferences("user-b") == {}

