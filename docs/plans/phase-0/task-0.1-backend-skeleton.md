# Task 0.1: 后端项目骨架 + 工程门禁

## 输入条件

- 仓库根目录存在，无 `backend/` 目录
- Python 3.11+ 已安装

## 输出物

- 创建: `backend/main.py`
- 创建: `backend/config.py`
- 创建: `backend/requirements.txt`
- 创建: `backend/requirements-dev.txt`
- 创建: `backend/pyproject.toml`（ruff + mypy + pytest 配置）
- 创建: `backend/api/__init__.py`
- 创建: `backend/api/health.py`
- 创建: `backend/services/__init__.py`
- 创建: `backend/engines/__init__.py`
- 创建: `backend/models/__init__.py`
- 创建: `backend/db/__init__.py`
- 创建: `backend/scripts/generate_openapi.py`（空壳，Task 0.5 填充）
- 创建: `backend/tests/__init__.py`
- 创建: `backend/tests/conftest.py`
- 创建: `backend/tests/test_health.py`

## 禁止修改

- 不修改 `frontend/` 目录下任何文件
- 不修改 `docs/` 目录下任何文件（openapi.json 由 Task 0.5 处理）

## 实现规格

### config.py

```python
import os

class Settings:
    HOST: str = "127.0.0.1"                          # 固定绑定本地，禁止 0.0.0.0
    PORT: int = int(os.getenv("PORT", "17396"))
    SESSION_TOKEN: str = os.getenv("SESSION_TOKEN", "")
    DEV_MODE: bool = os.getenv("DEV_MODE", "").lower() in ("1", "true")
    APP_DATA_DIR: str = os.getenv("APP_DATA_DIR", os.path.expanduser("~/.price-comparison-scanner"))

settings = Settings()
```

### main.py

```python
import argparse
from fastapi import FastAPI
from api.health import router as health_router
from config import settings

app = FastAPI(
    title="三方比价支出依据扫描工具",
    version="0.1.0",
)

# 路由注册
app.include_router(health_router, prefix="/api")

# 注意：不添加 CORSMiddleware。开发模式下通过 Vite proxy 解决跨域。
# Session Token 中间件在 Task 0.2 中添加。

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=settings.HOST)
    parser.add_argument("--port", type=int, default=settings.PORT)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    if args.token:
        settings.SESSION_TOKEN = args.token
    uvicorn.run(app, host=args.host, port=args.port)
```

### api/health.py

```python
from fastapi import APIRouter

router = APIRouter(tags=["系统"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

### requirements.txt

```txt
fastapi==0.115.6
uvicorn==0.34.0
pdfplumber==0.11.4
pypdf==5.1.0
python-docx==1.1.2
openpyxl==3.1.5
pandas==2.2.3
rapidfuzz==3.11.0
loguru==0.7.3
Pillow==11.1.0
```

### requirements-dev.txt

```txt
-r requirements.txt
pytest==8.3.4
pytest-anyio==0.0.0
httpx==0.28.1
anyio==4.8.0
ruff==0.8.6
mypy==1.14.1
```

### pyproject.toml

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### tests/conftest.py

```python
import pytest
from httpx import ASGITransport, AsyncClient
from main import app

@pytest.fixture
async def client():
    """无认证的测试客户端（用于测试公开端点）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

### tests/test_health.py

```python
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
```

## 测试与验收

```bash
cd backend
pip install -r requirements-dev.txt

# 门禁检查
ruff check .                           # exit 0
mypy . --ignore-missing-imports        # exit 0
pytest -x -q                           # 2 passed

# 启动验证
DEV_MODE=1 python main.py &
sleep 2
curl -sf http://127.0.0.1:17396/api/health | python -c "
import sys, json; assert json.load(sys.stdin) == {'status': 'ok'}
"
kill %1
```

**断言清单：**
- `ruff check .` → 退出码 0
- `mypy .` → 退出码 0
- `pytest` → 2 个测试通过
- `GET /api/health` → `{"status": "ok"}`，状态码 200
- `POST /api/health` → 状态码 405
- `backend/` 目录结构与 phase-spec 目录规范一致

## 提交

```bash
git add backend/
git commit -m "Phase 0.1: 后端项目骨架 + 工程门禁（ruff/mypy/pytest）"
```
