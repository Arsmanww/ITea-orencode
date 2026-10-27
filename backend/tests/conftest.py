"""Фикстуры pytest.

Тесты работают на отдельной базе fsp_test: она создаётся заново на каждый запуск и наполняется
настоящими миграциями Alembic (заодно проверяется, что миграции применяются с нуля).
Каждый тест идёт в транзакции, которая откатывается, поэтому тесты не влияют друг на друга
и не трогают демо-данные.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

# имя БД подменяем ДО импорта приложения: настройки читаются при импорте
TEST_DB = "fsp_test"
os.environ["POSTGRES_DB"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


async def _admin(sql: str) -> None:
    conn = await asyncpg.connect(
        user=settings.postgres_user, password=settings.postgres_password, host=settings.postgres_host,
        port=settings.postgres_port, database="postgres",
    )
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def database():
    asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    asyncio.run(_admin(f'CREATE DATABASE "{TEST_DB}"'))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, cwd=ROOT, env=os.environ.copy(), capture_output=True)
    yield
    asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        outer = await conn.begin()
        async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False) as s:
            yield s
        await outer.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
