import argparse
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.comparison import router as comparison_router
from api.compliance import router as compliance_router
from api.export import router as export_router
from api.files import router as files_router
from api.grouping import router as grouping_router
from api.health import router as health_router
from api.middleware import SessionTokenMiddleware
from api.problems import router as problems_router
from api.projects import router as projects_router
from api.requirements import router as requirements_router
from api.rules import router as rules_router
from api.shutdown import router as shutdown_router
from api.standardization import router as standardization_router
from api.tasks import router as tasks_router
from config import error_logger, settings

app = FastAPI(
    title="三方比价支出依据扫描工具",
    version="0.1.0",
)

# 中间件注册
# 注意：FastAPI 中间件执行顺序与添加顺序相反（后添加的先执行）
# SessionTokenMiddleware 先添加（内层），CORSMiddleware 后添加（外层先执行）
# 这样 CORS 先处理 OPTIONS preflight，再由 SessionToken 校验实际请求
app.add_middleware(SessionTokenMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
        "http://localhost:1420",
        "http://localhost:5173",
        "http://localhost:9527",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(health_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(rules_router, prefix="/api")
app.include_router(standardization_router, prefix="/api")
app.include_router(grouping_router, prefix="/api")
app.include_router(requirements_router, prefix="/api")
app.include_router(compliance_router, prefix="/api")
app.include_router(comparison_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(problems_router, prefix="/api")
app.include_router(shutdown_router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    error_logger.error(
        f"Unhandled exception: {request.method} {request.url.path}\n{''.join(tb)}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {type(exc).__name__}: {str(exc)}"},
    )


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
