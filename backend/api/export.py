from __future__ import annotations

from fastapi import APIRouter

from api.deps import get_app_data_dir, get_project_db
from models.comparison import ExportResponse
from services.report_service import ReportService

router = APIRouter(tags=["导出"])


@router.post("/projects/{project_id}/export", response_model=ExportResponse)
async def export_report(project_id: str) -> ExportResponse:
    """导出 Excel 审计底稿（异步任务）"""
    from engines.task_manager import get_task_manager

    app_data = get_app_data_dir()
    output_dir = str(app_data / "projects" / project_id / "exports")

    db = get_project_db(project_id)
    service = ReportService(db)

    tm = get_task_manager()
    task_id = tm.submit(
        "export",
        lambda progress_cb, pid=project_id, od=output_dir: service.export_report(pid, od),
        project_id,
    )
    return ExportResponse(task_id=task_id)
