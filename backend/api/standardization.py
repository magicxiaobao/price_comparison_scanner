from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.standardization import (
    FieldModifyRequest,
    FieldModifyResponse,
    StandardizedRowResponse,
    StandardizeRequest,
    StandardizeTaskResponse,
)
from services.project_service import ProjectService

router = APIRouter(tags=["标准化"])


def _get_service() -> ProjectService:
    return ProjectService()


@router.post(
    "/projects/{project_id}/standardize",
    response_model=StandardizeTaskResponse,
)
async def run_standardization(
    project_id: str, req: StandardizeRequest | None = None
) -> StandardizeTaskResponse:
    """执行标准化（异步），返回 task_id"""
    service = _get_service()
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    force = req.force if req else False
    task_id = service.run_standardization(project_id, force=force)
    return StandardizeTaskResponse(task_id=task_id)


@router.get(
    "/projects/{project_id}/standardized-rows",
    response_model=list[StandardizedRowResponse],
)
async def get_standardized_rows(
    project_id: str,
) -> list[StandardizedRowResponse]:
    """获取标准化结果"""
    service = _get_service()
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    rows = service.get_standardized_rows(project_id)
    return [StandardizedRowResponse(**r) for r in rows]


@router.put(
    "/standardized-rows/{row_id}",
    response_model=FieldModifyResponse,
)
async def modify_standardized_row(
    row_id: str, req: FieldModifyRequest
) -> FieldModifyResponse:
    """手工修正字段值，触发 AuditLog 记录 + 失效传播"""
    service = _get_service()
    try:
        result = service.modify_standardized_row(row_id, req.field, req.new_value)
    except ValueError as e:
        msg = str(e)
        if "不存在" in msg:
            raise HTTPException(status_code=404, detail=msg) from None
        raise HTTPException(status_code=400, detail=msg) from None
    return FieldModifyResponse(**result)


@router.get("/projects/{project_id}/column-mapping-info")
async def get_column_mapping_info(project_id: str) -> list[dict]:
    """获取项目的列名映射信息（供 ColumnMappingPanel 使用）"""
    service = _get_service()
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return service.get_column_mapping_info(project_id)
