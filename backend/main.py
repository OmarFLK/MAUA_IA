"""API intermediária para a API OpenAI-compatible Barô da Mauá."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from backend import database
from backend.assistants import AssistantMode, AssistantRegistry, CMobAssistant, GeneralAssistant
from backend.auth import get_current_user, hash_password, router as auth_router
from backend.config import settings
from backend.conversations import (
    add_turn,
    load_state,
    recent_turns,
    router as conversations_router,
)
from backend.models import User
from semob_ai.analytics import AnalyticsExecutor, QueryPlan
from semob_ai.analytics.catalog import TABLES
from semob_ai.conversation.service import ConversationEngine


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.25, ge=0, le=2)
    max_tokens: int = Field(default=1200, ge=64, le=8192)
    thinking: bool = False
    conversation_id: str = Field(default="default", min_length=1, max_length=100)
    assistant: AssistantMode = AssistantMode.CMOB

    @field_validator("messages")
    @classmethod
    def final_message_must_be_user(cls, messages: list[Message]) -> list[Message]:
        if messages[-1].role != "user":
            raise ValueError("A última mensagem deve ser do usuário.")
        return messages


logger = logging.getLogger("uvicorn.error")
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SYSTEM_PROMPTS = {
    AssistantMode.CMOB: (PROMPTS_DIR / "cmob_system.md").read_text(encoding="utf-8"),
    AssistantMode.GENERAL: (PROMPTS_DIR / "general_system.md").read_text(encoding="utf-8"),
}
conversation_engine = ConversationEngine(settings.semob_database_file, None, logger)


def get_assistant_registry() -> AssistantRegistry:
    return AssistantRegistry(
        CMobAssistant(conversation_engine, settings.semob_rag_file),
        GeneralAssistant(),
    )


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
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(auth_router)
app.include_router(conversations_router)


def configuration_error() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "API Barô ainda não configurada. Defina BARO_API_KEY no arquivo .env."
        },
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "configured": settings.configured,
        "database_ready": database.database_ready,
        "model": settings.baro_model,
        "supports_thinking": settings.baro_supports_thinking,
        "analytics_ready": settings.semob_database_file.is_file(),
        "rag_ready": settings.semob_rag_file.is_file(),
    }


@app.get("/api/ready")
async def readiness() -> JSONResponse:
    ready = await database.check_database()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "database_ready": ready,
            "ai_configured": settings.configured,
        },
    )


@app.get("/api/models", response_model=None)
async def models(_current_user: Annotated[User, Depends(get_current_user)]) -> JSONResponse | dict[str, Any]:
    if not settings.configured:
        return configuration_error()

    try:
        async with AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.baro_api_key,
            timeout=15.0,
        ) as client:
            response = await client.models.list()
            return {
                "object": "list",
                "data": [model.model_dump(mode="json") for model in response.data],
            }
    except (APIConnectionError, APIStatusError, APITimeoutError) as exc:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Não foi possível consultar os modelos da Barô: {friendly_error(exc)}"},
        )


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, APITimeoutError):
        return "o servidor demorou mais que o limite configurado para responder"
    if isinstance(exc, APIStatusError):
        return f"o servidor respondeu com HTTP {exc.status_code}"
    if isinstance(exc, APIConnectionError):
        return "não foi possível conectar à API Barô; confira a conexão e a URL configurada"
    return str(exc)


def ndjson(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def completion_payload(request: ChatRequest, rag_context: str = "") -> dict[str, Any]:
    controlled_messages = [{"role": "system", "content": SYSTEM_PROMPTS[request.assistant]}]
    if rag_context:
        controlled_messages[0]["content"] += "\n\nCONTEXTO PARA A MENSAGEM ATUAL:\n" + rag_context
    controlled_messages.extend(
        message.model_dump()
        for message in request.messages[-30:]
        if message.role in {"user", "assistant"}
    )
    payload: dict[str, Any] = {
        "model": settings.baro_model,
        "messages": controlled_messages,
        "temperature": min(request.temperature, 0.3),
        "max_tokens": request.max_tokens,
        "stream": True,
    }
    if settings.baro_supports_thinking:
        payload["extra_body"] = {"chat_template_kwargs": {"enable_thinking": request.thinking}}
    return payload


async def stream_completion(request: ChatRequest, rag_context: str = "") -> AsyncIterator[str]:
    payload = completion_payload(request, rag_context)
    timeout = httpx.Timeout(
        connect=10.0,
        read=settings.baro_timeout_seconds,
        write=30.0,
        pool=10.0,
    )

    try:
        async with AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.baro_api_key,
            timeout=timeout,
        ) as client:
            stream = await client.chat.completions.create(**payload)
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield ndjson({"type": "delta", "content": delta.content})
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning and request.thinking:
                        yield ndjson({"type": "reasoning", "content": reasoning})

                usage = getattr(chunk, "usage", None)
                if usage:
                    yield ndjson({"type": "usage", "usage": usage.model_dump(mode="json")})

            yield ndjson({"type": "done"})
    except (APIConnectionError, APIStatusError, APITimeoutError, OSError) as exc:
        yield ndjson({"type": "error", "message": friendly_error(exc)})


async def stream_local_answer(answer: str) -> AsyncIterator[str]:
    yield ndjson({"type": "delta", "content": answer})
    yield ndjson({"type": "done"})


async def remember(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    assistant: AssistantMode = AssistantMode.CMOB,
) -> None:
    try:
        await add_turn(
            user_id,
            conversation_id,
            role,
            content,
            assistant_mode=assistant.value,
        )
    except (OSError, ValueError, SQLAlchemyError):
        logger.exception("Não foi possível registrar a memória no banco.")


async def recover_history(request: ChatRequest, user_id: str) -> ChatRequest:
    messages = [message for message in request.messages if message.role in {"user", "assistant"}]
    if len(messages) == 1:
        try:
            turns = await recent_turns(
                user_id,
                request.conversation_id,
                limit=29,
                assistant_mode=request.assistant.value,
            )
            messages = [Message(role=turn.role, content=turn.content) for turn in turns] + messages
        except (OSError, ValueError, SQLAlchemyError):
            logger.exception("Não foi possível recuperar a memória do banco.")
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
                logger.warning("baro_completion_error: %s", payload.get("message"))
                if fallback_answer and not answer_parts:
                    fallback_answer = "Não consegui obter a interpretação do modelo agora. Seguem os resultados calculados localmente:\n\n" + fallback_answer
                    yield ndjson({"type": "delta", "content": fallback_answer})
                    await remember(user_id, request.conversation_id, "assistant", fallback_answer, request.assistant)
                    yield ndjson({"type": "done"})
                    return
                yield event
                return
        except json.JSONDecodeError:
            pass
        yield event
    answer = "".join(answer_parts).strip()
    if not answer and fallback_answer:
        logger.warning("baro_completion_empty: using local calculations")
        answer = "O modelo não retornou texto. Seguem os resultados calculados localmente:\n\n" + fallback_answer
        yield ndjson({"type": "delta", "content": answer})
    if answer:
        await remember(user_id, request.conversation_id, "assistant", answer, request.assistant)
    yield ndjson({"type": "done"})


@app.post("/api/semob/query")
async def semob_query(
    plan: QueryPlan,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    executor = AnalyticsExecutor(settings.semob_database_file)
    result = executor.execute(plan)
    return asdict(result)


@app.get("/api/semob/catalog")
async def semob_catalog(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    manifest_file = Path(__file__).resolve().parent.parent / "data/public/manifest.json"
    if not settings.semob_database_file.is_file() or not manifest_file.is_file():
        raise HTTPException(status_code=503, detail="CMob analytical snapshot is not available")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    return {
        "data_version": manifest["data_version"],
        "tables": {
            name: {
                **{key: table[key] for key in ("row_count", "start", "end", "periods")},
                "dimensions": sorted(TABLES[name]["dimensions"]),
                "metrics": {key: {"label": metric.label, "unit": metric.unit}
                            for key, metric in TABLES[name]["metrics"].items()},
            }
            for name, table in manifest["tables"].items() if name in TABLES
        },
    }


@app.get("/api/debug/session")
async def debug_session(
    current_user: Annotated[User, Depends(get_current_user)],
    conversation_id: str = Query(min_length=1, max_length=100),
    assistant: AssistantMode = Query(default=AssistantMode.CMOB),
) -> dict[str, Any]:
    if not settings.development:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = str(current_user.id)
    state = await load_state(user_id, conversation_id, assistant.value)
    recent = await recent_turns(
        user_id, conversation_id, limit=12, assistant_mode=assistant.value
    )
    return {
        "assistant": assistant.value,
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
    request = await recover_history(request, user_id)
    await remember(user_id, request.conversation_id, "user", question, request.assistant)
    try:
        prepared = await get_assistant_registry().get(request.assistant).prepare(
            user_id,
            request.conversation_id,
            question,
            history=[message.model_dump() for message in request.messages[:-1]],
        )
    except FileNotFoundError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    conversation = prepared.conversation
    if settings.development and conversation is not None:
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
                    "assistant": request.assistant.value,
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    if prepared.local_only:
        answer = prepared.answer or "Não foi possível concluir a análise."
        await remember(user_id, request.conversation_id, "assistant", answer, request.assistant)
        return StreamingResponse(stream_local_answer(answer), media_type="application/x-ndjson")

    if prepared.kind == "analytics" and not settings.configured:
        answer = prepared.answer or "Não foi possível concluir a análise."
        await remember(user_id, request.conversation_id, "assistant", answer, request.assistant)
        return StreamingResponse(stream_local_answer(answer), media_type="application/x-ndjson")

    if not settings.configured:
        return configuration_error()
    return StreamingResponse(
        stream_and_remember(
            request,
            prepared.llm_context,
            user_id,
            fallback_answer=prepared.answer,
        ),
        media_type="application/x-ndjson",
    )
