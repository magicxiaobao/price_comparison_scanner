import pytest


@pytest.mark.anyio
async def test_health_no_token_required(client):
    """GET /api/health 不需要 token"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_docs_no_token_required(client):
    """Swagger 文档不需要 token"""
    resp = await client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_protected_endpoint_without_token(client):
    """受保护端点无 token -> 403"""
    resp = await client.get("/api/projects")
    # 中间件在路由匹配前拦截，所以应该是 403
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_protected_endpoint_wrong_token(client):
    """错误 token -> 403"""
    resp = await client.get(
        "/api/projects",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_protected_endpoint_correct_token(authed_client):
    """正确 token -> 不是 403（可能 404 因路由不存在）"""
    resp = await authed_client.get("/api/projects")
    assert resp.status_code != 403


@pytest.mark.anyio
async def test_dev_mode_skips_auth(client, monkeypatch):
    """DEV_MODE=1 时跳过认证"""
    monkeypatch.setenv("DEV_MODE", "1")
    import config
    from config import Settings

    config.settings = Settings()
    # 注意：_isolate_settings fixture 会在测试结束后自动恢复 settings

    resp = await client.get("/api/projects")
    # DEV_MODE 下无 token 也不应返回 403
    assert resp.status_code != 403
