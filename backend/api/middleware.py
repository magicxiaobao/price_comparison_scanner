import hmac
import logging
import time

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
        access = _get_access_logger()
        start = time.time()

        # 认证检查（非开发模式）
        if not config.settings.DEV_MODE and request.method != "OPTIONS":
            path = request.url.path
            if not any(path.startswith(p) for p in PUBLIC_PREFIXES):
                auth = request.headers.get("Authorization", "")
                expected = f"Bearer {config.settings.SESSION_TOKEN}"
                if not config.settings.SESSION_TOKEN or not hmac.compare_digest(auth, expected):
                    elapsed_ms = int((time.time() - start) * 1000)
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
                    access.info(
                        "%s %s 403 %dms auth=no ua=%s origin=%s",
                        request.method, request.url.path, elapsed_ms,
                        request.headers.get("user-agent", "?")[:40],
                        request.headers.get("origin", "none"),
                    )
                    return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        response = await call_next(request)
        elapsed_ms = int((time.time() - start) * 1000)
        status = response.status_code

        # 记录请求到 access.log（含状态码和耗时）
        access.info(
            "%s %s %d %dms auth=%s ua=%s origin=%s",
            request.method, request.url.path, status, elapsed_ms,
            "yes" if request.headers.get("Authorization") else "no",
            request.headers.get("user-agent", "?")[:40],
            request.headers.get("origin", "none"),
        )

        # 4xx/5xx 错误额外记录到 error.log
        if status >= 400:
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk if isinstance(chunk, bytes) else chunk.encode()
            body_text = body_bytes.decode("utf-8", errors="replace")[:200]
            error_logger.error(
                "HTTP %d: %s %s content-type=%s body=%s",
                status, request.method, request.url.path,
                request.headers.get("content-type", "none"),
                body_text,
            )
            # 重建响应（body_iterator 已被消费）
            from starlette.responses import Response
            return Response(
                content=body_bytes,
                status_code=status,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response
