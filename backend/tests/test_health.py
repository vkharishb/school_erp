import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data


@pytest.mark.asyncio
async def test_docs_available(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200
