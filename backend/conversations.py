from __future__ import annotations

import uuid
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.config import settings
from backend.database import get_session, session_scope
from backend.models import (
    Conversation,
    ConversationMessage,
    ConversationStateRecord,
    User,
    UserPreference,
)
from semob_ai.conversation.models import ConversationState
from semob_ai.memory import MemoryTurn


router = APIRouter(prefix="/api", tags=["conversas"])


class MessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    reasoning: str | None
    feedback: str | None
    usage: dict[str, Any] | None
    duration_ms: float | None
    ttft_ms: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: str
    title: str
    assistant_mode: Literal["cmob", "general"]
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse]


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class ConversationCreate(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=100)
    title: str = Field(default="Nova conversa", min_length=1, max_length=80)
    assistant_mode: Literal["cmob", "general"] = "cmob"


class PreferencesUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class ImportedMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=100_000)
    reasoning: str | None = Field(default=None, max_length=100_000)
    created_at: datetime


class ConversationImport(ConversationCreate):
    id: str = Field(min_length=1, max_length=100)
    messages: list[ImportedMessage] = Field(max_length=1000)


class ConversationRewind(BaseModel):
    message_id: int = Field(ge=1)
    last_message_id: int = Field(ge=1)


def _deleted_key(public_id: str) -> str:
    return 'deleted-chat:' + hashlib.sha256(public_id.encode()).hexdigest()


async def _find_conversation(
    session: AsyncSession,
    user_id: uuid.UUID,
    public_id: str,
) -> Conversation | None:
    return await session.scalar(
        select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.public_id == public_id,
        )
    )


async def _ensure_conversation(
    session: AsyncSession,
    user_id: uuid.UUID,
    public_id: str,
    assistant_mode: str,
    title: str | None = None,
) -> Conversation:
    conversation = await _find_conversation(session, user_id, public_id)
    if conversation:
        if conversation.assistant_mode != assistant_mode:
            raise ValueError("O identificador da conversa já pertence a outro assistente.")
        return conversation
    if await session.get(UserPreference, (user_id, _deleted_key(public_id))):
        raise HTTPException(status_code=409, detail='Esta conversa foi excluida da conta.')
    conversation = Conversation(
        user_id=user_id,
        public_id=public_id,
        assistant_mode=assistant_mode,
        title=(title or "Nova conversa")[:80],
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def add_turn(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    assistant_mode: str = "cmob",
    *,
    reasoning: str | None = None,
    usage: dict[str, Any] | None = None,
    duration_ms: float | None = None,
    ttft_ms: float | None = None,
) -> None:
    if role not in {"user", "assistant"}:
        raise ValueError("Papel de memória inválido.")
    owner_id = uuid.UUID(user_id)
    async with session_scope() as session:
        conversation = await _ensure_conversation(
            session,
            owner_id,
            conversation_id,
            assistant_mode,
            title=content if role == "user" else None,
        )
        if role == "user" and conversation.title == "Nova conversa":
            conversation.title = content[:80]
        conversation.updated_at = datetime.now(timezone.utc)
        session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role=role,
                content=content,
                reasoning=reasoning,
                usage=usage,
                duration_ms=duration_ms,
                ttft_ms=ttft_ms,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.semob_memory_retention_days),
            )
        )


async def recent_turns(
    user_id: str,
    conversation_id: str,
    limit: int = 12,
    assistant_mode: str = "cmob",
) -> list[MemoryTurn]:
    owner_id = uuid.UUID(user_id)
    async with session_scope() as session:
        conversation = await _find_conversation(session, owner_id, conversation_id)
        if not conversation or conversation.assistant_mode != assistant_mode:
            return []
        rows = list(
            await session.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.expires_at > datetime.now(timezone.utc),
                )
                .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
                .limit(min(limit, 50))
            )
        )
    return [
        MemoryTurn(item.role, item.content, item.created_at.isoformat())
        for item in reversed(rows)
    ]


async def load_state(
    user_id: str,
    conversation_id: str,
    assistant_mode: str = "cmob",
) -> ConversationState:
    owner_id = uuid.UUID(user_id)
    async with session_scope() as session:
        conversation = await _find_conversation(session, owner_id, conversation_id)
        if not conversation or conversation.assistant_mode != assistant_mode:
            return ConversationState(user_id=user_id, session_id=conversation_id)
        record = await session.get(ConversationStateRecord, conversation.id)
        if not record:
            return ConversationState(user_id=user_id, session_id=conversation_id)
        return ConversationState.model_validate(record.state_json)


async def save_state(state: ConversationState, assistant_mode: str = "cmob") -> None:
    owner_id = uuid.UUID(state.user_id)
    async with session_scope() as session:
        conversation = await _ensure_conversation(
            session,
            owner_id,
            state.session_id,
            assistant_mode,
        )
        record = await session.get(ConversationStateRecord, conversation.id)
        payload = state.model_dump(mode="json")
        if record:
            record.state_json = payload
            record.updated_at = datetime.now(timezone.utc)
        else:
            session.add(ConversationStateRecord(conversation_id=conversation.id, state_json=payload))


async def purge_expired_turns() -> int:
    async with session_scope() as session:
        result = await session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.expires_at <= datetime.now(timezone.utc)
            )
        )
        return result.rowcount or 0


def _summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.public_id,
        title=conversation.title,
        assistant_mode=conversation.assistant_mode,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ConversationSummary]:
    conversations = list(
        await session.scalars(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
    )
    return [_summary(item) for item in conversations]


@router.post(
    "/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationSummary:
    public_id = request.id or str(uuid.uuid4())
    if await _find_conversation(session, current_user.id, public_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conversa já existente.")
    conversation = await _ensure_conversation(
        session,
        current_user.id,
        public_id,
        request.assistant_mode,
        title=" ".join(request.title.split()),
    )
    await session.commit()
    await session.refresh(conversation)
    return _summary(conversation)


@router.get('/conversation-history', response_model=list[ConversationDetail])
async def conversation_history(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> list[ConversationDetail]:
    conversations = list(await session.scalars(select(Conversation).where(
        Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc(), Conversation.id).offset(offset).limit(limit)))
    if not conversations:
        return []
    messages = await session.scalars(select(ConversationMessage).where(
        ConversationMessage.conversation_id.in_([item.id for item in conversations])
    ).order_by(ConversationMessage.created_at, ConversationMessage.id))
    grouped = defaultdict(list)
    for message in messages:
        grouped[message.conversation_id].append(message)
    return [ConversationDetail(**_summary(item).model_dump(), messages=grouped[item.id]) for item in conversations]


@router.post('/conversations/import', response_model=ConversationSummary | None)
async def import_conversation(
    request: ConversationImport,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationSummary | None:
    if sum(len(message.content) + len(message.reasoning or '') for message in request.messages) > 2_000_000:
        raise HTTPException(status_code=413, detail='Conversa muito grande para importar.')
    if await session.get(UserPreference, (current_user.id, _deleted_key(request.id))):
        return None
    conversation = await _ensure_conversation(session, current_user.id, request.id, request.assistant_mode, request.title)
    existing = list(await session.scalars(select(ConversationMessage).where(
        ConversationMessage.conversation_id == conversation.id).order_by(ConversationMessage.created_at, ConversationMessage.id)))
    # Never overwrite cloud history with an old device's divergent or shorter cache.
    prefix_matches = len(existing) <= len(request.messages) and all(
        saved.role == cached.role and saved.content == cached.content
        for saved, cached in zip(existing, request.messages))
    if prefix_matches:
        original_count = len(existing)
        for message in request.messages[len(existing):]:
            created_at = message.created_at.replace(tzinfo=timezone.utc) if message.created_at.tzinfo is None else message.created_at
            if existing:
                previous = existing[-1].created_at
                previous = previous.replace(tzinfo=timezone.utc) if previous.tzinfo is None else previous
                created_at = max(created_at, previous + timedelta(microseconds=1))
            record = ConversationMessage(conversation_id=conversation.id, role=message.role,
                content=message.content, reasoning=message.reasoning, created_at=created_at,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.semob_memory_retention_days))
            session.add(record)
            existing.append(record)
        if len(request.messages) > original_count:
            conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conversation)
    return _summary(conversation)


@router.post('/conversations/{conversation_id}/clear', status_code=204, response_class=Response)
async def clear_conversation(
    conversation_id: str, current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    conversation = await _find_conversation(session, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversa nao encontrada.')
    await session.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id == conversation.id))
    await session.execute(delete(ConversationStateRecord).where(ConversationStateRecord.conversation_id == conversation.id))
    key = _deleted_key(conversation_id)
    if not await session.get(UserPreference, (current_user.id, key)):
        session.add(UserPreference(user_id=current_user.id, key=key, value='cleared'))
    conversation.title = 'Nova conversa'
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=204)


@router.post('/conversations/{conversation_id}/rewind', status_code=204, response_class=Response)
async def rewind_conversation(
    conversation_id: str, request: ConversationRewind,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    conversation = await _find_conversation(session, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversa nao encontrada.')
    latest = await session.scalar(select(func.max(ConversationMessage.id)).where(ConversationMessage.conversation_id == conversation.id))
    target = await session.get(ConversationMessage, request.message_id)
    if not target or target.conversation_id != conversation.id or target.role != 'user':
        raise HTTPException(status_code=404, detail='Mensagem nao encontrada.')
    if latest != request.last_message_id:
        raise HTTPException(status_code=409, detail='A conversa foi atualizada em outro dispositivo. Recarregue antes de gerar novamente.')
    await session.execute(delete(ConversationMessage).where(
        ConversationMessage.conversation_id == conversation.id, ConversationMessage.id >= request.message_id))
    await session.execute(delete(ConversationStateRecord).where(ConversationStateRecord.conversation_id == conversation.id))
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=204)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationDetail:
    conversation = await _find_conversation(session, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    messages = list(
        await session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )
    return ConversationDetail(**_summary(conversation).model_dump(), messages=messages)


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationSummary:
    conversation = await _find_conversation(session, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    conversation.title = " ".join(request.title.split())
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conversation)
    return _summary(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_conversation(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    conversation = await _find_conversation(session, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    await session.delete(conversation)
    key = _deleted_key(conversation_id)
    if not await session.get(UserPreference, (current_user.id, key)):
        session.add(UserPreference(user_id=current_user.id, key=key, value=True))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/preferences", response_model=dict[str, Any])
async def get_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    rows = list(
        await session.scalars(
            select(UserPreference).where(UserPreference.user_id == current_user.id)
        )
    )
    return {item.key: item.value for item in rows if not item.key.startswith('deleted-chat:')}


@router.put("/preferences", response_model=dict[str, Any])
async def put_preferences(
    request: PreferencesUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    if len(request.values) > 100 or any(not key or len(key) > 80 or key.startswith('deleted-chat:') for key in request.values):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Preferências inválidas.")
    existing = {
        item.key: item
        for item in await session.scalars(
            select(UserPreference).where(UserPreference.user_id == current_user.id)
        )
    }
    for key, value in request.values.items():
        if key in existing:
            existing[key].value = value
            existing[key].updated_at = datetime.now(timezone.utc)
        else:
            session.add(UserPreference(user_id=current_user.id, key=key, value=value))
    await session.commit()
    return request.values
