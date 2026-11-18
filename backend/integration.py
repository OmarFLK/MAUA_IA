"""Server-to-server access to the CMob pipeline. Never exposes general Gemma."""
from __future__ import annotations

import asyncio
import calendar
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from backend import database
from backend.config import settings
from backend.models import User
from semob_ai.analytics.query_plan import DatePeriod

router = APIRouter(prefix="/api/integrations/semob", tags=["Integração SEMOB"])
bearer = HTTPBearer(auto_error=False)
_limits: dict[str, tuple[int, float]] = {}
_active = asyncio.Semaphore(4)


def require_integration_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = settings.semob_integration_key_sha256
    if not expected:
        raise HTTPException(503, "Integração SEMOB não configurada.")
    token = credentials.credentials if credentials else ""
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not token.startswith("maua_semob_") or len(token) > 256 or not hmac.compare_digest(digest, expected):
        raise HTTPException(401, "Credencial de integração inválida.", headers={"WWW-Authenticate": "Bearer"})


class IntegrationFilters(BaseModel):
    from_date: date | None = Field(default=None, alias="from")
    to_date: date | None = Field(default=None, alias="to")


class IntegrationContext(BaseModel):
    # Existing SEMOB context includes coverage/insights. Those are not trusted
    # evidence: the CMob pipeline retrieves its own knowledge and analytics.
    period: str | None = Field(default=None, pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    filters: IntegrationFilters = Field(default_factory=IntegrationFilters)

    @model_validator(mode="after")
    def validate_date_range(self) -> IntegrationContext:
        self.date_period()
        return self

    def date_period(self) -> DatePeriod | None:
        start = end = None
        if self.period:
            year, month = map(int, self.period.split("-"))
            start, end = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        if self.filters.from_date:
            start = max(start, self.filters.from_date) if start else self.filters.from_date
        if self.filters.to_date:
            end = min(end, self.filters.to_date) if end else self.filters.to_date
        if start and end and start > end:
            raise ValueError("Intervalo de datas fora do período selecionado.")
        return DatePeriod(start=start, end=end) if start or end else None


class IntegrationChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(min_length=1, max_length=160)
    conversation_id: str = Field(default="workspace", min_length=1, max_length=100)
    context: IntegrationContext = Field(default_factory=IntegrationContext)
    preferences: dict[str, Any] = Field(default_factory=dict)


class IntegrationChatResponse(BaseModel):
    answer: str
    assistant: str = "cmob"
    kind: str
    sources: list[str]
    conversation_id: str
    period: str | None


def _check_rate(owner: str) -> None:
    now = time.monotonic()
    for key, (_, until) in list(_limits.items()):
        if until <= now:
            _limits.pop(key, None)
    for key, maximum in (("service", 120), (owner, 20)):
        count, until = _limits.get(key, (0, now + 60))
        if count >= maximum or len(_limits) > 5000:
            raise HTTPException(429, "Limite temporário da IA. Aguarde um minuto.", headers={"Retry-After": "60"})
        _limits[key] = (count + 1, until)


async def integration_user(external_id: str) -> User:
    """Inactive identities isolate SEMOB history from every MAUA login account."""
    from backend.auth import hash_password

    identity = uuid.uuid5(uuid.NAMESPACE_URL, "maua-ia:semob:" + external_id)
    async with database.session_scope() as session:
        user = await session.get(User, identity)
        if user:
            return user
        user = User(
            id=identity, name="Integração SEMOB",
            email=f"{identity.hex}@semob.integration.invalid",
            password_hash=hash_password(secrets.token_urlsafe(48)), is_active=False,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            user = await session.get(User, identity)
            if user is None:
                raise
        return user


@router.get("/status", dependencies=[Depends(require_integration_key)])
async def integration_status() -> dict[str, Any]:
    ready = database.database_ready and settings.semob_rag_file.is_file() and settings.semob_database_file.is_file()
    return {"configured": ready and settings.configured, "assistant": "cmob", "rag_ready": settings.semob_rag_file.is_file(), "analytics_ready": settings.semob_database_file.is_file()}


@router.post("/chat", response_model=IntegrationChatResponse, dependencies=[Depends(require_integration_key)])
async def integration_chat(payload: IntegrationChatRequest) -> IntegrationChatResponse:
    # Import at request time to keep the shared pipeline's module graph acyclic.
    from backend import main

    if not database.database_ready or not settings.semob_rag_file.is_file() or not settings.semob_database_file.is_file():
        raise HTTPException(503, "A base RAG ou analítica da IA não está disponível.")
    owner = hashlib.sha256(payload.user_id.encode()).hexdigest()
    _check_rate(owner)
    # A dashboard period change begins an independent analytical context.
    context_key = payload.context.period or ""
    if payload.context.filters.from_date or payload.context.filters.to_date:
        context_key += f":{payload.context.filters.from_date}:{payload.context.filters.to_date}"
    conversation_id = "semob:" + hashlib.sha256(f"{payload.conversation_id}:{context_key}".encode()).hexdigest()
    if _active.locked():
        raise HTTPException(429, "A IA está atendendo outras solicitações. Tente novamente.", headers={"Retry-After": "5"})
    async with _active:
        user = await integration_user(payload.user_id)
        user_id = str(user.id)
        await main.purge_expired_turns(user.id)
        request = main.ChatRequest(
            messages=[main.Message(role="user", content=payload.message)],
            conversation_id=conversation_id, assistant=main.AssistantMode.CMOB,
        )
        request = await main.recover_history(request, user_id)
        prepared = await main.get_assistant_registry().get(main.AssistantMode.CMOB).prepare(
            user_id, conversation_id, payload.message,
            history=[message.model_dump() for message in request.messages[:-1]],
            default_period=payload.context.date_period(),
        )
        if prepared.kind == "analytics_unavailable":
            raise HTTPException(503, "A base analítica da IA não está disponível.")
        sources = list(prepared.sources)
        state = prepared.conversation.state if prepared.conversation else None
        if state and state.previous_query_result_summary:
            for result in state.previous_query_result_summary.values():
                if isinstance(result, dict) and result.get("source_table"):
                    sources.append(f"CMob: {result['source_table']}")
        if prepared.local_only or prepared.kind == "analytics":
            # Preserve exact calculated results, dates and coverage. Do not ask
            # a language model to rewrite verified operational numbers.
            answer = prepared.answer or "Não foi possível concluir a análise."
        else:
            if not settings.configured:
                raise HTTPException(503, "O modelo da IA não está configurado.")
            parts = []
            try:
                async with asyncio.timeout(45):
                    async for event in main.stream_completion(request, prepared.llm_context):
                        item = json.loads(event)
                        if item.get("type") == "error":
                            raise HTTPException(502, "A IA não conseguiu concluir a resposta. Tente novamente.")
                        if item.get("type") == "delta":
                            parts.append(item.get("content", ""))
            except TimeoutError:
                raise HTTPException(504, "A IA demorou para responder. Tente novamente.") from None
            answer = "".join(parts).strip()
            if not answer:
                raise HTTPException(502, "A IA não retornou uma resposta.")
        # Save successful exchanges only. Rejected/failed attempts do not enter
        # the model's conversation history on a subsequent retry.
        await main.remember(user_id, conversation_id, "user", payload.message, main.AssistantMode.CMOB)
        await main.remember(user_id, conversation_id, "assistant", answer, main.AssistantMode.CMOB)
        return IntegrationChatResponse(answer=answer, kind=prepared.kind, sources=list(dict.fromkeys(sources)), conversation_id=payload.conversation_id, period=payload.context.period)
