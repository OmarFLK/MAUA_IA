from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.models import Base, User


engine = create_async_engine(settings.database_url, pool_pre_ping=True) if settings.database_configured else None
SessionFactory = async_sessionmaker(engine, expire_on_commit=False) if engine else None
database_ready = False

TEST_USERS = (
    ("Ana Silva", "ana@teste.maua.ai"),
    ("Bruno Santos", "bruno@teste.maua.ai"),
    ("Carla Oliveira", "carla@teste.maua.ai"),
)


async def initialize_database(hash_password) -> None:
    global database_ready
    if not engine or not SessionFactory:
        return

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    database_ready = True

    if not settings.seed_test_users:
        return

    async with SessionFactory() as session:
        existing = set(
            await session.scalars(select(User.email).where(User.email.in_([item[1] for item in TEST_USERS])))
        )
        for name, email in TEST_USERS:
            if email not in existing:
                if len(settings.seed_test_password) < 8:
                    raise ValueError("Defina SEED_TEST_PASSWORD com pelo menos 8 caracteres no .env local para criar contas demonstrativas.")
                session.add(User(name=name, email=email, password_hash=hash_password(settings.seed_test_password)))
        await session.commit()


async def close_database() -> None:
    if engine:
        await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    if not database_ready or not SessionFactory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados indisponível. Confira a variável DATABASE_URL.",
        )
    async with SessionFactory() as session:
        yield session

