from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import get_project_db
from models.comparison import ComparisonGenerateResponse, ComparisonResultResponse
from services.comparison_service import ComparisonService

router = APIRouter(tags=["比价"])


def _get_service(project_id: str) -> ComparisonService:
    db = get_project_db(project_id)
    return ComparisonService(db)


@router.post(
    "/projects/{project_id}/comparison/generate",
    response_model=ComparisonGenerateResponse,
)
async def generate_comparison(project_id: str) -> ComparisonGenerateResponse:
    """生成比价结果（异步任务）

    [M10] 前置检查：项目需有已确认归组，否则返回 422。
    [M11] 前端通过 GET /api/tasks/{task_id}/status 轮询进度，间隔 2 秒，超时 300 秒。
    """
    from engines.task_manager import get_task_manager

    service = _get_service(project_id)

    # [M10] 检查是否有已确认归组
    db = get_project_db(project_id)
    with db.read() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM commodity_groups WHERE project_id = ? AND status = 'confirmed'",
            (project_id,),
        )
        row = cursor.fetchone()
        count: int = row[0] if row else 0
    if count == 0:
        raise HTTPException(status_code=422, detail="请先完成商品归组")

    tm = get_task_manager()
    task_id = tm.submit(
        "comparison",
        lambda progress_cb, pid=project_id: service.generate_comparison(pid),
        project_id,
    )
    return ComparisonGenerateResponse(task_id=task_id)


@router.get(
    "/projects/{project_id}/comparison",
    response_model=list[ComparisonResultResponse],
)
async def get_comparison(project_id: str) -> list[ComparisonResultResponse]:
    """获取比价结果"""
    service = _get_service(project_id)
    return service.list_results(project_id)
