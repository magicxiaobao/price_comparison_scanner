from fastapi import APIRouter, File, HTTPException, UploadFile

from models.file import (
    FileUploadResponse,
    SupplierConfirmRequest,
    SupplierFileResponse,
)
from models.table import RawTableResponse, TableToggleRequest, TableToggleResponse
from services.file_service import FileService
from services.project_service import ProjectService

router = APIRouter(tags=["文件导入"])
file_service = FileService()
project_service = ProjectService()


@router.post("/projects/{project_id}/files", response_model=FileUploadResponse)
async def upload_file(project_id: str, file: UploadFile = File(...)):  # noqa: B008
    """上传供应商文件，异步解析，返回 task_id 和 file_id"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    content = await file.read()
    try:
        result = file_service.import_file(project_id, file.filename or "unknown", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return result


@router.get("/projects/{project_id}/files", response_model=list[SupplierFileResponse])
async def list_files(project_id: str):
    """获取项目的所有已导入文件"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return file_service.get_files(project_id)


@router.put("/files/{file_id}/confirm-supplier", response_model=SupplierFileResponse)
async def confirm_supplier(file_id: str, body: SupplierConfirmRequest):
    """确认供应商名称"""
    project = project_service.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = file_service.confirm_supplier(file_id, body.supplier_name, body.project_id)
    if not result:
        raise HTTPException(status_code=404, detail="文件不存在")
    return result


@router.get("/projects/{project_id}/tables", response_model=list[RawTableResponse])
async def list_tables(project_id: str):
    """获取项目的所有解析表格"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return file_service.get_tables(project_id)


@router.put("/tables/{table_id}/toggle-selection", response_model=TableToggleResponse)
async def toggle_table_selection(table_id: str, body: TableToggleRequest):
    """切换表格参与比价状态"""
    project = project_service.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = file_service.toggle_table_selection(table_id, body.project_id)
    if not result:
        raise HTTPException(status_code=404, detail="表格不存在")
    return {"table_id": result["id"], "selected": bool(result["selected"])}
