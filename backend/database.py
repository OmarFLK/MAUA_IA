from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import event, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.models import Base, User


def _engine_options(url: str) -> dict[str, Any]:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        if ":memory:" in url:
            options["poolclass"] = StaticPool
        return options
    options.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
    return options


def _build_engine() -> AsyncEngine | None:
    if not settings.database_configured:
        return None
    url = settings.sqlalchemy_database_url
    return create_async_engine(url, **_engine_options(url))


engine = _build_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False) if engine else None
database_ready = False

if engine and settings.sqlalchemy_database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

TEST_USERS = (
    ("Ana Silva", "ana@teste.maua.ai"),
    ("Bruno Santos", "bruno@teste.maua.ai"),
    ("Carla Oliveira", "carla@teste.maua.ai"),
)


async def _required_schema_exists(connection) -> bool:
    required = {
        "users",
        "conversations",
        "conversation_messages",
        "conversation_states",
        "user_preferences",
    }
    tables = await connection.run_sync(
        lambda sync_connection: set(inspect(sync_connection).get_table_names())
    )
    return required.issubset(tables)


async def initialize_database(hash_password) -> None:
    global database_ready
    database_ready = False
    if not engine or not SessionFactory:
        return

    async with engine.begin() as connection:
        if settings.database_auto_create:
            await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("SELECT 1"))
        if not await _required_schema_exists(connection):
            raise RuntimeError("Schema do banco ausente. Execute `alembic upgrade head` antes de iniciar a API.")
    database_ready = True

    if not settings.seed_test_users:
        return
    if len(settings.seed_test_password) < 8:
        raise ValueError(
            "Defina SEED_TEST_PASSWORD com pelo menos 8 caracteres no .env local para criar contas demonstrativas."
        )

    async with session_scope() as session:
        existing = set(
            await session.scalars(select(User.email).where(User.email.in_([item[1] for item in TEST_USERS])))
        )
        for name, email in TEST_USERS:
            if email not in existing:
                session.add(User(name=name, email=email, password_hash=hash_password(settings.seed_test_password)))


async def check_database() -> bool:
    global database_ready
    if not engine:
        database_ready = False
        return False
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            database_ready = await _required_schema_exists(connection)
    except Exception:
        database_ready = False
    return database_ready


async def close_database() -> None:
    global database_ready
    database_ready = False
    if engine:
        await engine.dispose()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if not SessionFactory:
        raise RuntimeError("DATABASE_URL não configurada.")
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    if not database_ready or not SessionFactory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados indisponível. Confira DATABASE_URL e execute as migrações.",
        )
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
