from __future__ import annotations

from pydantic import BaseModel, Field

from models.standardization import _CAMEL_CONFIG

# ================================================================
# 需求标准
# ================================================================


class RequirementCreate(BaseModel):
    """创建需求项请求"""

    model_config = _CAMEL_CONFIG

    code: str | None = None
    category: str = Field(
        ..., pattern=r"^(功能要求|技术规格|商务条款|服务要求|交付要求)$"
    )
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    is_mandatory: bool = True
    match_type: str = Field(..., pattern=r"^(keyword|numeric|manual)$")
    expected_value: str | None = None
    operator: str | None = Field(None, pattern=r"^(gte|lte|eq|range)$")


class RequirementUpdate(BaseModel):
    """更新需求项请求"""

    model_config = _CAMEL_CONFIG

    project_id: str
    code: str | None = None
    category: str | None = Field(
        None, pattern=r"^(功能要求|技术规格|商务条款|服务要求|交付要求)$"
    )
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    is_mandatory: bool | None = None
    match_type: str | None = Field(None, pattern=r"^(keyword|numeric|manual)$")
    expected_value: str | None = None
    operator: str | None = Field(None, pattern=r"^(gte|lte|eq|range)$")


class RequirementResponse(BaseModel):
    """需求项响应"""

    model_config = _CAMEL_CONFIG

    id: str
    project_id: str
    code: str | None = None
    category: str
    title: str
    description: str | None = None
    is_mandatory: bool
    match_type: str
    expected_value: str | None = None
    operator: str | None = None
    sort_order: int
    created_at: str


# ================================================================
# 需求标准导入
# ================================================================


class RequirementImportResult(BaseModel):
    """需求标准导入结果"""

    model_config = _CAMEL_CONFIG

    total: int
    imported: int
    skipped: int
    errors: list[str]


# ================================================================
# 符合性匹配
# ================================================================


class ComplianceMatchResponse(BaseModel):
    """单条符合性匹配结果"""

    model_config = _CAMEL_CONFIG

    id: str
    requirement_item_id: str
    commodity_group_id: str
    supplier_file_id: str
    supplier_name: str
    status: str  # match / partial / no_match / unclear
    is_acceptable: bool
    match_score: float | None = None
    evidence_text: str | None = None
    evidence_location: str | None = None  # JSON 字符串
    match_method: str | None = None  # keyword / numeric / manual
    needs_review: bool
    confirmed_at: str | None = None


class ComplianceConfirmRequest(BaseModel):
    """确认匹配结果请求"""

    model_config = _CAMEL_CONFIG

    project_id: str
    status: str = Field(
        ..., pattern=r"^(match|partial|no_match|unclear)$"
    )


class ComplianceAcceptRequest(BaseModel):
    """标记部分符合为可接受请求"""

    model_config = _CAMEL_CONFIG

    project_id: str
    is_acceptable: bool


class ComplianceMatrixCell(BaseModel):
    """符合性矩阵单元格"""

    model_config = _CAMEL_CONFIG

    match_id: str
    status: str
    is_acceptable: bool
    needs_review: bool
    evidence_text: str | None = None


class ComplianceMatrixRow(BaseModel):
    """符合性矩阵一行（一个需求项）"""

    model_config = _CAMEL_CONFIG

    requirement: RequirementResponse
    suppliers: dict[str, ComplianceMatrixCell]  # key: supplier_file_id


class ComplianceMatrixResponse(BaseModel):
    """符合性矩阵完整响应"""

    model_config = _CAMEL_CONFIG

    supplier_names: dict[str, str]  # key: supplier_file_id, value: supplier_name
    rows: list[ComplianceMatrixRow]


class ComplianceEvaluateResponse(BaseModel):
    """符合性匹配任务响应"""

    model_config = _CAMEL_CONFIG

    task_id: str
