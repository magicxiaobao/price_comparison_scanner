from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import get_project_db
from models.compliance import (
    ComplianceAcceptRequest,
    ComplianceConfirmRequest,
    ComplianceEvaluateResponse,
    ComplianceMatrixResponse,
)
from services.compliance_service import ComplianceService

router = APIRouter(tags=["符合性审查"])


def _get_service(project_id: str) -> ComplianceService:
    db = get_project_db(project_id)
    return ComplianceService(db)


@router.post(
    "/projects/{project_id}/compliance/evaluate",
    response_model=ComplianceEvaluateResponse,
)
async def evaluate_compliance(project_id: str) -> ComplianceEvaluateResponse:
    """执行符合性匹配（异步任务）"""
    from engines.task_manager import get_task_manager

    service = _get_service(project_id)
    tm = get_task_manager()
    task_id = tm.submit(
        "compliance_evaluate",
        lambda progress_cb, pid=project_id: service.evaluate(pid),
        project_id,
    )
    return ComplianceEvaluateResponse(task_id=task_id)


@router.get(
    "/projects/{project_id}/compliance/matrix",
    response_model=ComplianceMatrixResponse,
)
async def get_compliance_matrix(project_id: str) -> ComplianceMatrixResponse:
    """获取符合性矩阵"""
    service = _get_service(project_id)
    return service.get_matrix(project_id)


@router.put("/compliance/{match_id}/confirm")
async def confirm_match(match_id: str, req: ComplianceConfirmRequest) -> dict:
    """确认匹配结果。请求体含 project_id + status"""
    service = _get_service(req.project_id)
    match = service.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    return service.confirm_match(match_id, req.status)


@router.put("/compliance/{match_id}/accept")
async def accept_match(match_id: str, req: ComplianceAcceptRequest) -> dict:
    """标记部分符合为可接受。请求体含 project_id + is_acceptable"""
    service = _get_service(req.project_id)
    match = service.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    return service.accept_match(match_id, req.is_acceptable)
