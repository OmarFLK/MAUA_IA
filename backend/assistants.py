from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from backend.conversations import load_state, save_state
from semob_ai.conversation.models import ConversationResponse
from semob_ai.conversation.service import ConversationEngine
from semob_ai.guardrails.scope import is_conversational_message
from semob_ai.rag import LocalRagIndex


class AssistantMode(str, Enum):
    CMOB = "cmob"
    GENERAL = "general"


@dataclass(frozen=True)
class PreparedAssistantResponse:
    mode: AssistantMode
    kind: str
    answer: str | None = None
    llm_context: str = ""
    local_only: bool = False
    conversation: ConversationResponse | None = None


class AssistantPipeline(Protocol):
    mode: AssistantMode
    adapter_name: str | None

    async def prepare(
        self,
        user_id: str,
        conversation_id: str,
        question: str,
        history: list[dict[str, str]],
    ) -> PreparedAssistantResponse: ...


class CMobAssistant:
    """Specialized pipeline. A future CMob adapter belongs here, not in the shared provider."""

    mode = AssistantMode.CMOB
    adapter_name: str | None = None

    def __init__(self, engine: ConversationEngine, rag_database: Path):
        self.engine = engine
        self.rag_database = rag_database

    async def prepare(
        self,
        user_id: str,
        conversation_id: str,
        question: str,
        history: list[dict[str, str]],
    ) -> PreparedAssistantResponse:
        state = await load_state(user_id, conversation_id, assistant_mode=self.mode.value)
        try:
            conversation = self.engine.handle(
                user_id,
                conversation_id,
                question,
                history=history,
                state=state,
            )
        except FileNotFoundError:
            return PreparedAssistantResponse(
                mode=self.mode,
                kind="analytics_unavailable",
                answer=(
                    "A base analitica da SEMOB ainda nao esta carregada neste servidor. "
                    "Nao vou inventar numeros: para responder essa consulta, o Render precisa receber "
                    "o arquivo autorizado `semob.duckdb` configurado em `SEMOB_DATABASE_PATH`."
                ),
                local_only=True,
            )
        if conversation.kind == "analytics":
            await save_state(conversation.state, assistant_mode=self.mode.value)
            if conversation.resolution.plan and conversation.resolution.plan.dimensions:
                return PreparedAssistantResponse(
                    mode=self.mode, kind=conversation.kind, answer=conversation.answer,
                    local_only=True, conversation=conversation,
                )
        if conversation.kind in {"out_of_scope", "clarification"}:
            return PreparedAssistantResponse(
                mode=self.mode,
                kind=conversation.kind,
                answer=conversation.answer,
                local_only=True,
                conversation=conversation,
            )

        rag_query = (
            conversation.resolution.resolved_question
            if conversation.resolution.is_follow_up
            else question
        )
        social = is_conversational_message(question)
        chunks = []
        if not social and conversation.kind != "analytics":
            chunks = LocalRagIndex(self.rag_database).search(rag_query, limit=4)

        context_parts = [conversation.llm_context] if conversation.llm_context else []
        if social:
            context_parts.append(
                "A mensagem atual é uma interação social, não uma consulta de dados. "
                "Responda brevemente sem repetir resultados anteriores."
            )
        context_parts.extend(
            f"[{chunk.source}#trecho-{chunk.chunk_index}] {chunk.text}" for chunk in chunks
        )
        return PreparedAssistantResponse(
            mode=self.mode,
            kind=conversation.kind,
            answer=conversation.answer,
            llm_context="\n\n".join(context_parts),
            conversation=conversation,
        )


class GeneralAssistant:
    """General-purpose pipeline with no CMob retrieval, analytics, guardrails or state."""

    mode = AssistantMode.GENERAL
    adapter_name: str | None = None

    async def prepare(
        self,
        user_id: str,
        conversation_id: str,
        question: str,
        history: list[dict[str, str]],
    ) -> PreparedAssistantResponse:
        del user_id, conversation_id, question, history
        return PreparedAssistantResponse(mode=self.mode, kind="general")


class AssistantRegistry:
    def __init__(self, *pipelines: AssistantPipeline):
        self._pipelines = {pipeline.mode: pipeline for pipeline in pipelines}

    def get(self, mode: AssistantMode) -> AssistantPipeline:
        return self._pipelines[mode]
