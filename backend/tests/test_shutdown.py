import pytest


@pytest.mark.anyio
async def test_shutdown_returns_shutting_down(authed_client):
    resp = await authed_client.post("/api/shutdown")
    assert resp.status_code == 200
    assert resp.json() == {"status": "shutting_down"}


@pytest.mark.anyio
async def test_shutdown_requires_auth(client):
    resp = await client.post("/api/shutdown")
    assert resp.status_code == 403
