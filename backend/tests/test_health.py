import pytest


@pytest.mark.anyio
async def test_health_returns_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok"}


@pytest.mark.anyio
async def test_health_is_get_only(client):
    resp = await client.post("/api/health")
    assert resp.status_code == 405
