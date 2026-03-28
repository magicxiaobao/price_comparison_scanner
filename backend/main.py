import argparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from config import settings

app = FastAPI(
    title="三方比价支出依据扫描工具",
    version="0.1.0",
)

# 中间件注册（CORS 必须在 SessionToken 之前，以处理 preflight 请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://localhost:1420",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionTokenMiddleware)

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
