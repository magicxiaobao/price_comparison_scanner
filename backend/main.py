import argparse

from fastapi import FastAPI

from api.health import router as health_router
from api.middleware import SessionTokenMiddleware
from config import settings

app = FastAPI(
    title="三方比价支出依据扫描工具",
    version="0.1.0",
)

# 中间件注册
app.add_middleware(SessionTokenMiddleware)

# 路由注册
app.include_router(health_router, prefix="/api")

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
