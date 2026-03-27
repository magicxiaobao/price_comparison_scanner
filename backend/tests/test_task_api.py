import pytest


@pytest.mark.anyio
async def test_get_task_status_not_found(authed_client):
    resp = await authed_client.get("/api/tasks/nonexistent-id/status")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_cancel_task_not_found(authed_client):
    resp = await authed_client.delete("/api/tasks/nonexistent-id")
    assert resp.status_code == 404
