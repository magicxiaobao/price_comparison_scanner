import argparse

from fastapi import FastAPI

from api.files import router as files_router
from api.compliance import router as compliance_router
from api.grouping import router as grouping_router
from api.requirements import router as requirements_router
from api.health import router as health_router
from api.middleware import SessionTokenMiddleware
from api.projects import router as projects_router
from api.rules import router as rules_router
from api.standardization import router as standardization_router
from api.tasks import router as tasks_router
from config import settings

app = FastAPI(
    title="三方比价支出依据扫描工具",
    version="0.1.0",
)

# 中间件注册
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

# 注意：不添加 CORSMiddleware。开发模式下通过 Vite proxy 解决跨域。

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
