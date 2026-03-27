from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(params=["asyncio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """
    每个测试独立的 settings 实例。
    测试默认运行在非 DEV_MODE，需要 token。
    fixture 结束后自动恢复原始 settings（通过 monkeypatch 的自动清理）。
    """
    monkeypatch.setenv("DEV_MODE", "")
    monkeypatch.setenv("SESSION_TOKEN", "test-token-abc")
    # 重新加载 config 使环境变量生效
    import config
    from config import Settings

    original = config.settings
    config.settings = Settings()
    yield
    # monkeypatch 自动恢复环境变量，这里显式恢复 settings 对象
    config.settings = original


@pytest.fixture
async def client():
    """无认证的测试客户端"""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def authed_client():
    """带认证 token 的测试客户端"""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token-abc"},
    ) as c:
        yield c
