from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.deps import get_app_data_dir, get_project_db
from models.compliance import (
    RequirementCreate,
    RequirementImportResult,
    RequirementResponse,
    RequirementUpdate,
)
from services.compliance_service import ComplianceService

router = APIRouter(tags=["需求标准"])


def _get_service(project_id: str) -> ComplianceService:
    db = get_project_db(project_id)
    return ComplianceService(db)


@router.post(
    "/projects/{project_id}/requirements", response_model=RequirementResponse
)
async def create_requirement(
    project_id: str, req: RequirementCreate
) -> RequirementResponse:
    service = _get_service(project_id)
    return service.create_requirement(project_id, req)


@router.get(
    "/projects/{project_id}/requirements",
    response_model=list[RequirementResponse],
)
async def list_requirements(project_id: str) -> list[RequirementResponse]:
    service = _get_service(project_id)
    return service.list_requirements(project_id)


@router.put("/requirements/{req_id}", response_model=RequirementResponse)
async def update_requirement(
    req_id: str, req: RequirementUpdate
) -> RequirementResponse:
    """更新需求项。请求体含 project_id"""
    service = _get_service(req.project_id)
    item = service.repo.get_by_id(req_id)
    if not item:
        raise HTTPException(status_code=404, detail="需求项不存在")
    try:
        return service.update_requirement(req_id, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/requirements/{req_id}")
async def delete_requirement(req_id: str, project_id: str) -> dict:
    """删除需求项。project_id 通过查询参数传入"""
    service = _get_service(project_id)
    item = service.repo.get_by_id(req_id)
    if not item:
        raise HTTPException(status_code=404, detail="需求项不存在")
    deleted = service.delete_requirement(req_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="需求项不存在")
    return {"detail": "已删除"}


@router.post(
    "/projects/{project_id}/requirements/import",
    response_model=RequirementImportResult,
)
async def import_requirements(
    project_id: str, file: UploadFile = File(...)  # noqa: B008
) -> RequirementImportResult:
    """从模板 Excel 导入需求标准"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        service = _get_service(project_id)
        return service.import_requirements(project_id, tmp_path)
    finally:
        os.unlink(tmp_path)


@router.get("/projects/{project_id}/requirements/export")
async def export_requirements(project_id: str) -> FileResponse:
    """导出需求标准模板 Excel"""
    app_data = get_app_data_dir()
    output_path = str(
        app_data / "projects" / project_id / "exports" / "requirements_template.xlsx"
    )
    service = _get_service(project_id)
    service.export_requirements(project_id, output_path)
    return FileResponse(output_path, filename="需求标准模板.xlsx")
