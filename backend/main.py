"""API intermediária para o servidor OpenAI-compatible da Mauá."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend import database
from backend.auth import get_current_user, hash_password, router as auth_router
from backend.config import settings
from backend.models import User
from semob_ai.analytics import AnalyticsExecutor, QueryPlan
from semob_ai.conversation.service import ConversationEngine
from semob_ai.conversation.store import SessionStore
from semob_ai.memory import MemoryStore
from semob_ai.guardrails.scope import is_conversational_message
from semob_ai.rag import LocalRagIndex


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.25, ge=0, le=2)
    max_tokens: int = Field(default=1200, ge=64, le=8192)
    thinking: bool = False
    conversation_id: str = Field(default="default", min_length=1, max_length=100)

    @field_validator("messages")
    @classmethod
    def final_message_must_be_user(cls, messages: list[Message]) -> list[Message]:
        if messages[-1].role != "user":
            raise ValueError("A última mensagem deve ser do usuário.")
        return messages


logger = logging.getLogger("uvicorn.error")
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "system.md"
SYSTEM_PROMPT = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
conversation_engine = ConversationEngine(settings.semob_database_file, settings.semob_session_file, logger)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_configured:
        try:
            await database.initialize_database(hash_password)
        except Exception:
            logger.exception("Não foi possível inicializar o banco de dados.")
    yield
    await database.close_database()


app = FastAPI(title="cMob AI - SEMOB", version="1.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(auth_router)


def auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.maua_ai_api_key}",
        "Content-Type": "application/json",
    }


def configuration_error() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Servidor da Mauá ainda não configurado. Defina MAUA_AI_BASE_URL no arquivo .env."
        },
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "configured": settings.configured,
        "database_ready": database.database_ready,
        "model": settings.maua_ai_model,
        "supports_thinking": settings.maua_ai_supports_thinking,
        "analytics_ready": settings.semob_database_file.is_file(),
    }


@app.get("/api/models", response_model=None)
async def models(_current_user: Annotated[User, Depends(get_current_user)]) -> JSONResponse | dict[str, Any]:
    if not settings.configured:
        return configuration_error()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{settings.base_url}/models", headers=auth_headers())
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Não foi possível consultar os modelos da Mauá: {friendly_error(exc)}"},
        )


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "o servidor demorou mais que o limite configurado para responder"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"o servidor respondeu com HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.ConnectError):
        return "não foi possível conectar ao servidor; confira a URL e a rede da Mauá"
    return str(exc)


def ndjson(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def completion_payload(request: ChatRequest, rag_context: str = "") -> dict[str, Any]:
    controlled_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if rag_context:
        controlled_messages[0]["content"] += "\n\nCONTEXTO PARA A MENSAGEM ATUAL:\n" + rag_context
    controlled_messages.extend(
        message.model_dump()
        for message in request.messages[-30:]
        if message.role in {"user", "assistant"}
    )
    payload: dict[str, Any] = {
        "model": settings.maua_ai_model,
        "messages": controlled_messages,
        "temperature": min(request.temperature, 0.3),
        "max_tokens": request.max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if settings.maua_ai_supports_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": request.thinking}
    return payload


async def stream_completion(request: ChatRequest, rag_context: str = "") -> AsyncIterator[str]:
    payload = completion_payload(request, rag_context)
    timeout = httpx.Timeout(
        connect=10.0,
        read=settings.maua_ai_timeout_seconds,
        write=30.0,
        pool=10.0,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.base_url}/chat/completions",
                headers=auth_headers(),
                json=payload,
            ) as response:
                if response.is_error:
                    body = (await response.aread()).decode(errors="replace")
                    detail = body[:500] or response.reason_phrase
                    yield ndjson({"type": "error", "message": f"HTTP {response.status_code}: {detail}"})
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        reasoning = delta.get("reasoning_content")
                        if content:
                            yield ndjson({"type": "delta", "content": content})
                        if reasoning and request.thinking:
                            yield ndjson({"type": "reasoning", "content": reasoning})

                    if chunk.get("usage"):
                        yield ndjson({"type": "usage", "usage": chunk["usage"]})

                yield ndjson({"type": "done"})
    except (httpx.HTTPError, OSError) as exc:
        yield ndjson({"type": "error", "message": friendly_error(exc)})


async def stream_local_answer(answer: str) -> AsyncIterator[str]:
    yield ndjson({"type": "delta", "content": answer})
    yield ndjson({"type": "done"})


def remember(user_id: str, conversation_id: str, role: str, content: str) -> None:
    try:
        MemoryStore(settings.semob_memory_file, settings.semob_memory_retention_days).add_turn(
            user_id, conversation_id, role, content
        )
    except (OSError, ValueError, sqlite3.Error):
        logger.exception("Não foi possível registrar a memória local.")


def recover_history(request: ChatRequest, user_id: str) -> ChatRequest:
    messages = [message for message in request.messages if message.role in {"user", "assistant"}]
    if len(messages) == 1:
        try:
            turns = MemoryStore(settings.semob_memory_file, settings.semob_memory_retention_days).recent(
                user_id, request.conversation_id, limit=29,
            )
            messages = [Message(role=turn.role, content=turn.content) for turn in turns] + messages
        except (OSError, ValueError, sqlite3.Error):
            logger.exception("Não foi possível recuperar a memória local.")
    return request.model_copy(update={"messages": messages})


async def stream_and_remember(
    request: ChatRequest,
    rag_context: str,
    user_id: str,
    fallback_answer: str | None = None,
) -> AsyncIterator[str]:
    answer_parts: list[str] = []
    async for event in stream_completion(request, rag_context):
        try:
            payload = json.loads(event)
            event_type = payload.get("type")
            if event_type == "delta" and payload.get("content"):
                answer_parts.append(payload["content"])
            elif event_type == "done":
                continue
            elif event_type == "error":
                logger.warning("maua_completion_error: %s", payload.get("message"))
                if fallback_answer and not answer_parts:
                    fallback_answer = "Não consegui obter a interpretação do modelo agora. Seguem os resultados calculados localmente:\n\n" + fallback_answer
                    yield ndjson({"type": "delta", "content": fallback_answer})
                    yield ndjson({"type": "done"})
                    remember(user_id, request.conversation_id, "assistant", fallback_answer)
                    return
                yield event
                return
        except json.JSONDecodeError:
            pass
        yield event
    answer = "".join(answer_parts).strip()
    if not answer and fallback_answer:
        logger.warning("maua_completion_empty: using local calculations")
        answer = "O modelo não retornou texto. Seguem os resultados calculados localmente:\n\n" + fallback_answer
        yield ndjson({"type": "delta", "content": answer})
    if answer:
        remember(user_id, request.conversation_id, "assistant", answer)
    yield ndjson({"type": "done"})


@app.post("/api/semob/query")
async def semob_query(
    plan: QueryPlan,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    executor = AnalyticsExecutor(settings.semob_database_file)
    result = executor.execute(plan)
    return asdict(result)


@app.get("/api/debug/session")
async def debug_session(
    current_user: Annotated[User, Depends(get_current_user)],
    conversation_id: str = Query(min_length=1, max_length=100),
) -> dict[str, Any]:
    if not settings.development:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = str(current_user.id)
    state = SessionStore(settings.semob_session_file).load(user_id, conversation_id)
    recent = MemoryStore(settings.semob_memory_file, settings.semob_memory_retention_days).recent(
        user_id, conversation_id, limit=12
    )
    return {
        **state.model_dump(mode="json"),
        "memory_items_recovered": [asdict(item) for item in recent],
    }


@app.post("/api/chat", response_model=None)
async def chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse | JSONResponse:
    question = request.messages[-1].content
    user_id = str(current_user.id)
    request = recover_history(request, user_id)
    remember(user_id, request.conversation_id, "user", question)
    try:
        conversation = conversation_engine.handle(
            user_id, request.conversation_id, question,
            history=[message.model_dump() for message in request.messages[:-1]],
        )
    except FileNotFoundError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    if settings.development:
        logger.info(
            "conversation_resolution %s",
            json.dumps(
                {
                    "original_question": question,
                    "is_follow_up": conversation.resolution.is_follow_up,
                    "follow_up_type": conversation.resolution.follow_up_type,
                    "resolved_intent": conversation.resolution.resolved_question,
                    "inherited_context": conversation.resolution.inherited_context,
                    "modified_context": conversation.resolution.modified_context,
                    "final_query_plan": conversation.resolution.plan.model_dump(mode="json") if conversation.resolution.plan else None,
                    "session_id": request.conversation_id,
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    if conversation.kind in {"out_of_scope", "clarification"}:
        answer = conversation.answer or "Não foi possível concluir a análise."
        remember(user_id, request.conversation_id, "assistant", answer)
        return StreamingResponse(stream_local_answer(answer), media_type="application/x-ndjson")

    if conversation.kind == "analytics" and not settings.configured:
        answer = conversation.answer or "Não foi possível concluir a análise."
        remember(user_id, request.conversation_id, "assistant", answer)
        return StreamingResponse(stream_local_answer(answer), media_type="application/x-ndjson")

    if not settings.configured:
        return configuration_error()
    rag_query = conversation.resolution.resolved_question if conversation.resolution.is_follow_up else question
    social = is_conversational_message(question)
    chunks = [] if social or conversation.kind == "analytics" else LocalRagIndex(settings.semob_rag_file).search(rag_query, limit=4)
    context_parts = [conversation.llm_context] if conversation.llm_context else []
    if social:
        context_parts.append("A mensagem atual é uma interação social, não uma consulta de dados. Responda brevemente sem repetir resultados anteriores.")
    context_parts.extend(
        f"[{chunk.source}#trecho-{chunk.chunk_index}] {chunk.text}" for chunk in chunks
    )
    rag_context = "\n\n".join(context_parts)
    return StreamingResponse(
        stream_and_remember(request, rag_context, user_id, fallback_answer=conversation.answer),
        media_type="application/x-ndjson",
    )
