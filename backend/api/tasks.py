from fastapi import APIRouter, HTTPException

from engines.task_manager import get_task_manager

router = APIRouter(tags=["异步任务"])


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    tm = get_task_manager()
    info = tm.get_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": info.task_id,
        "task_type": info.task_type,
        "status": info.status.value,
        "progress": info.progress,
        "error": info.error,
        "created_at": info.created_at,
        "started_at": info.started_at,
        "completed_at": info.completed_at,
    }


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    tm = get_task_manager()
    info = tm.get_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")
    cancelled = tm.cancel(task_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="任务无法取消（可能已在运行中）")
    return {"detail": "任务已取消"}
