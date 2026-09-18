"""API intermediária para o servidor OpenAI-compatible da Mauá."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend import database
from backend.auth import get_current_user, hash_password, router as auth_router
from backend.config import settings
from backend.models import User


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.25, ge=0, le=2)
    max_tokens: int = Field(default=1200, ge=64, le=8192)
    thinking: bool = False

    @field_validator("messages")
    @classmethod
    def final_message_must_be_user(cls, messages: list[Message]) -> list[Message]:
        if messages[-1].role != "user":
            raise ValueError("A última mensagem deve ser do usuário.")
        return messages


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_configured:
        try:
            await database.initialize_database(hash_password)
        except Exception:
            logger.exception("Não foi possível inicializar o banco de dados.")
    yield
    await database.close_database()


app = FastAPI(title="Mauá AI Chat", version="1.1.0", lifespan=lifespan)
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


async def stream_completion(request: ChatRequest) -> AsyncIterator[str]:
    payload: dict[str, Any] = {
        "model": settings.maua_ai_model,
        "messages": [message.model_dump() for message in request.messages],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        # Qwen raciocina bastante por padrão. O modo rápido economiza contexto.
        "chat_template_kwargs": {"enable_thinking": request.thinking},
    }
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


@app.post("/api/chat", response_model=None)
async def chat(
    request: ChatRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse | JSONResponse:
    if not settings.configured:
        return configuration_error()
    return StreamingResponse(stream_completion(request), media_type="application/x-ndjson")
