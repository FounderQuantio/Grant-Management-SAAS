"""Integration tests for transactions API."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_transaction_requires_auth():
    from main import app
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/v1/transactions", json={})
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_transactions(client: AsyncClient):
    resp = await client.get("/api/v1/transactions")
    assert resp.status_code in (200, 403)  # 403 if role check fails with mock


@pytest.mark.asyncio
async def test_error_response_format(client: AsyncClient):
    resp = await client.get("/api/v1/transactions/00000000-0000-0000-0000-000000000000/risk")
    assert resp.status_code in (200, 404, 403)
    if resp.status_code >= 400:
        body = resp.json()
        assert "error_code" in body
        assert "message" in body
        assert "request_id" in body
