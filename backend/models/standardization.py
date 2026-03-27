from __future__ import annotations

from pydantic import BaseModel, Field


class SourceLocationItem(BaseModel):
    """单个字段的来源定位"""

    type: str  # xlsx / docx / pdf / pdf_ocr
    sheet: str | None = None
    cell: str | None = None
    table_index: int | None = None
    row: int | None = None
    col: int | None = None
    page: int | None = None
    extraction_mode: str | None = None  # structure / ocr
    ocr_confidence: float | None = None


# source_location 类型：key 为标准字段名，value 为 SourceLocationItem
SourceLocation = dict[str, SourceLocationItem]


class HitRuleSnapshot(BaseModel):
    """规则命中快照"""

    rule_id: str
    rule_name: str
    match_content: str  # 如 "报价→unit_price"
    match_mode: str  # exact / fuzzy / regex


class StandardizedRowCreate(BaseModel):
    """标准化行写入模型"""

    id: str
    raw_table_id: str
    supplier_file_id: str
    row_index: int
    product_name: str | None = None
    spec_model: str | None = None
    unit: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None
    tax_rate: str | None = None
    delivery_period: str | None = None
    remark: str | None = None
    source_location: SourceLocation
    column_mapping: dict[str, str] | None = None
    hit_rule_snapshots: list[HitRuleSnapshot] | None = None
    confidence: float = 1.0
    needs_review: bool = False
    tax_basis: str | None = None  # known_inclusive / known_exclusive / unknown


class StandardizedRowResponse(BaseModel):
    """标准化行响应模型"""

    id: str
    raw_table_id: str = Field(..., alias="rawTableId")
    supplier_file_id: str = Field(..., alias="supplierFileId")
    row_index: int = Field(..., alias="rowIndex")
    product_name: str | None = None
    spec_model: str | None = None
    unit: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None
    tax_rate: str | None = None
    delivery_period: str | None = None
    remark: str | None = None
    source_location: SourceLocation = Field(..., alias="sourceLocation")
    column_mapping: dict[str, str] | None = Field(None, alias="columnMapping")
    hit_rule_snapshots: list[HitRuleSnapshot] | None = Field(
        None, alias="hitRuleSnapshots"
    )
    confidence: float = 1.0
    is_manually_modified: bool = Field(False, alias="isManuallyModified")
    needs_review: bool = Field(False, alias="needsReview")
    tax_basis: str | None = Field(None, alias="taxBasis")

    model_config = {"populate_by_name": True}


class FieldModifyRequest(BaseModel):
    """手工修正请求"""

    field: str
    new_value: str | float | None = Field(..., alias="newValue")

    model_config = {"populate_by_name": True}


class FieldModifyResponse(BaseModel):
    """手工修正响应"""

    success: bool
    audit_log: dict = Field(..., alias="auditLog")
    dirty_stages: list[str] = Field(default_factory=list, alias="dirtyStages")

    model_config = {"populate_by_name": True}


class StandardizeRequest(BaseModel):
    """标准化执行请求（异步）"""

    force: bool = False


class StandardizeTaskResponse(BaseModel):
    """标准化执行响应"""

    task_id: str = Field(..., alias="taskId")

    model_config = {"populate_by_name": True}
