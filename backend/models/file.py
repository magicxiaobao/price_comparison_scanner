
from pydantic import BaseModel, Field


class SupplierFileCreate(BaseModel):
    """文件上传后内部使用的创建模型（API 层不直接用，由 service 构造）"""
    project_id: str
    supplier_name: str
    original_filename: str
    file_path: str
    file_type: str = Field(..., pattern=r"^(xlsx|docx|pdf|image)$")
    recognition_mode: str = Field(default="structure", pattern=r"^(structure|ocr|manual)$")


class SupplierFileResponse(BaseModel):
    """API 返回的文件信息"""
    id: str
    project_id: str
    supplier_name: str
    supplier_confirmed: bool
    original_filename: str
    file_path: str
    file_type: str
    recognition_mode: str | None = None
    imported_at: str


class SupplierConfirmRequest(BaseModel):
    """确认供应商名称请求"""
    supplier_name: str = Field(..., min_length=1, max_length=200)
    project_id: str


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    task_id: str
    supplier_name_guess: str
