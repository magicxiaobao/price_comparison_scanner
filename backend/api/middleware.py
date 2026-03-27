from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import config

# 不需要认证的路径前缀
PUBLIC_PREFIXES = ("/api/health", "/docs", "/redoc", "/openapi.json")


class SessionTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # 开发模式跳过认证
        if config.settings.DEV_MODE:
            return await call_next(request)

        # 公开路径跳过认证
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # 校验 token
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {config.settings.SESSION_TOKEN}"
        if not config.settings.SESSION_TOKEN or auth != expected:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        return await call_next(request)
