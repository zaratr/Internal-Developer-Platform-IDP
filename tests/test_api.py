import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import Role, create_access_token
from app.db.session import Base, get_db
from app.main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


@pytest.fixture(scope="session", autouse=True)
async def prepare_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


def auth_headers(role: str):
    token = create_access_token("tester", role, team_id=1)
    return {"Authorization": f"Bearer {token}"}


def test_register_service_and_provision_environment():
    client = TestClient(app)
    service_payload = {
        "name": "payment-api",
        "description": "handles payments",
        "tags": {"owner": "payments", "data_sensitivity": "internal"},
    }
    res = client.post("/api/services", json=service_payload, headers=auth_headers(Role.PLATFORM_ADMIN))
    assert res.status_code == 201, res.text
    service_id = res.json()["id"]

    env_payload = {"name": "dev", "tier": "dev", "config": {}}
    res = client.post(
        f"/api/services/{service_id}/environments",
        json=env_payload,
        headers=auth_headers(Role.PLATFORM_ADMIN),
    )
    assert res.status_code == 201, res.text
