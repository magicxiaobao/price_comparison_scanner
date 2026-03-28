import hmac
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import config
from config import error_logger

# 全量请求日志（写入 access.log）
_access_logger: logging.Logger | None = None


def _get_access_logger() -> logging.Logger:
    global _access_logger
    if _access_logger is None:
        from config import get_app_data_dir
        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _access_logger = logging.getLogger("price-comparison-access")
        handler = logging.FileHandler(log_dir / "access.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
        ))
        _access_logger.addHandler(handler)
        _access_logger.setLevel(logging.INFO)
    return _access_logger


# 不需要认证的路径前缀
PUBLIC_PREFIXES = ("/api/health", "/docs", "/redoc", "/openapi.json")


class SessionTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # 记录所有请求到 access.log
        access = _get_access_logger()
        access.info(
            "%s %s auth=%s ua=%s origin=%s",
            request.method, request.url.path,
            "yes" if request.headers.get("Authorization") else "no",
            request.headers.get("user-agent", "?")[:40],
            request.headers.get("origin", "none"),
        )

        # 开发模式跳过认证
        if config.settings.DEV_MODE:
            return await call_next(request)

        # CORS preflight (OPTIONS) 放行，由 CORSMiddleware 处理
        if request.method == "OPTIONS":
            return await call_next(request)

        # 公开路径跳过认证
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # 校验 token
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {config.settings.SESSION_TOKEN}"
        if not config.settings.SESSION_TOKEN or not hmac.compare_digest(auth, expected):
            error_logger.error(
                "Auth rejected: method=%s path=%s "
                "auth_header_present=%s auth_first20='%s' "
                "server_token_set=%s server_token_first8='%s' "
                "origin=%s user_agent=%s",
                request.method, request.url.path,
                bool(auth), auth[:20] if auth else "",
                bool(config.settings.SESSION_TOKEN),
                config.settings.SESSION_TOKEN[:8] if config.settings.SESSION_TOKEN else "",
                request.headers.get("origin", "none"),
                request.headers.get("user-agent", "none")[:50],
            )
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        return await call_next(request)
