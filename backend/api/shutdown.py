from fastapi import APIRouter

router = APIRouter(tags=["系统"])


@router.post("/shutdown")
async def shutdown():
    """优雅关闭 sidecar 进程。Tauri 退出时调用。"""
    import asyncio
    import os
    import signal

    async def _shutdown():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_shutdown())
    return {"status": "shutting_down"}
