# Task 0.2: Session Token 认证中间件

## 输入条件

- Task 0.1 完成（后端骨架 + config.py 存在）
- `backend/main.py` 可启动

## 输出物

- 创建: `backend/api/middleware.py`
- 修改: `backend/main.py`（注册中间件）
- 修改: `backend/tests/conftest.py`（添加带 token 的 client fixture）
- 创建: `backend/tests/test_middleware.py`

## 禁止修改

- 不修改 `api/health.py`
- 不修改 `requirements.txt` / `requirements-dev.txt`
- 不修改 `frontend/`

## 实现规格

### api/middleware.py

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings

# 不需要认证的路径前缀
PUBLIC_PREFIXES = ("/api/health", "/docs", "/redoc", "/openapi.json")

class SessionTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 开发模式跳过认证
        if settings.DEV_MODE:
            return await call_next(request)

        # 公开路径跳过认证
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # 校验 token
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.SESSION_TOKEN}"
        if not settings.SESSION_TOKEN or auth != expected:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        return await call_next(request)
```

**设计要点：**
- `DEV_MODE=1` 时全部放行，简化开发
- `SESSION_TOKEN` 为空时也拒绝（生产模式必须传 token）
- 公开路径用前缀匹配（`/docs` 是 FastAPI Swagger UI）
- 认证失败返回 403（不是 401，因为这不是传统的身份认证，是本地进程间认证）

### main.py 修改

在 `app` 创建后、路由注册前，添加：

```python
from api.middleware import SessionTokenMiddleware

app.add_middleware(SessionTokenMiddleware)
```

### tests/conftest.py 修改

**完全替换** Task 0.1 中的 conftest.py。使用 `yield` + 恢复模式确保 settings 不会在测试间串状态。

```python
import pytest
from httpx import ASGITransport, AsyncClient

@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
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
```

**设计要点：**
- `_isolate_settings` 是 `autouse=True`，每个测试自动隔离
- fixture 结束后显式恢复 `config.settings = original`，防止测试间串状态
- `monkeypatch` 自动清理环境变量，与 settings 恢复配合确保完全隔离

### tests/test_middleware.py

```python
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
    """受保护端点无 token → 403"""
    resp = await client.get("/api/projects")
    # 注意：此时 /api/projects 路由尚不存在，会返回 404 或 403
    # 中间件在路由匹配前拦截，所以应该是 403
    assert resp.status_code == 403

@pytest.mark.anyio
async def test_protected_endpoint_wrong_token(client):
    """错误 token → 403"""
    resp = await client.get(
        "/api/projects",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 403

@pytest.mark.anyio
async def test_protected_endpoint_correct_token(authed_client):
    """正确 token → 不是 403（可能 404 因路由不存在）"""
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
```

## 测试与验收

```bash
cd backend

# 门禁
ruff check .
mypy . --ignore-missing-imports
pytest -x -q                          # 预期 8 个测试通过（2 health + 6 middleware）

# 手动验证：非开发模式
SESSION_TOKEN=my-secret python main.py &
sleep 2
# 无 token → 403
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:17396/api/projects
# 预期：403
# 有 token → 非 403
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer my-secret" http://127.0.0.1:17396/api/projects
# 预期：404（路由不存在）但不是 403
# health 无需 token
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:17396/api/health
# 预期：200
kill %1
```

**断言清单：**
- `pytest` → 8 个测试通过
- 非开发模式：无 token 访问受保护端点 → 403
- 非开发模式：正确 token → 非 403
- 非开发模式：health 端点 → 200（无需 token）
- DEV_MODE=1：无 token 也不返回 403

## 提交

```bash
git add backend/api/middleware.py backend/main.py backend/tests/
git commit -m "Phase 0.2: Session Token 认证中间件（开发模式可跳过）"
```
