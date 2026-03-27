from typing import Any

from pydantic import BaseModel


class RawTableResponse(BaseModel):
    """API 返回的原始表格信息"""
    id: str
    supplier_file_id: str
    table_index: int
    sheet_name: str | None = None
    page_number: int | None = None
    row_count: int
    column_count: int
    raw_data: Any  # JSON 对象: {"headers": [...], "rows": [[...]]}
    selected: bool
    # 关联信息（来自 JOIN）
    supplier_name: str | None = None
    original_filename: str | None = None
    supplier_confirmed: bool | None = None


class TableToggleRequest(BaseModel):
    """表格选择切换请求"""
    project_id: str


class TableToggleResponse(BaseModel):
    """表格选择切换响应"""
    table_id: str
    selected: bool
