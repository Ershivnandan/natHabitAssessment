import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.core.cache as cache_module
from app.core.database import Base, get_session
from app.main import create_app


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(monkeypatch):
    """Route every get_redis() call through an in-memory Redis for tests."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_module, "_redis", client)
    yield client
    await client.flushall()


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client):
    """A client with a registered, logged-in user and bearer token applied."""
    creds = {"email": "shiv@example.com", "password": "shiv@123"}
    await client.post("/auth/signup", json=creds)
    resp = await client.post("/auth/login", json=creds)
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
