from __future__ import annotations

from pydantic import BaseModel

from models.standardization import _CAMEL_CONFIG

# ================================================================
# 供应商报价
# ================================================================


class SupplierPrice(BaseModel):
    """供应商报价（JSON 字段元素）"""

    model_config = _CAMEL_CONFIG

    supplier_file_id: str
    supplier_name: str
    unit_price: float | None = None
    total_price: float | None = None
    tax_basis: str | None = None  # 含税/不含税/未知
    unit: str | None = None
    compliance_status: str | None = None  # match / partial / no_match / unclear / None
    is_acceptable: bool | None = None


# ================================================================
# 异常
# ================================================================


class AnomalyDetail(BaseModel):
    """异常详情（JSON 字段元素）"""

    model_config = _CAMEL_CONFIG

    type: str  # tax_basis_mismatch / unit_mismatch / currency_mismatch / missing_required_field
    description: str
    blocking: bool  # 是否阻断比价结论
    affected_suppliers: list[str]


# ================================================================
# 比价结果
# ================================================================


class ComparisonResultResponse(BaseModel):
    """比价结果响应"""

    model_config = _CAMEL_CONFIG

    id: str
    group_id: str
    group_name: str
    project_id: str
    comparison_status: str  # comparable / blocked / partial
    supplier_prices: list[SupplierPrice]
    min_price: float | None = None
    effective_min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    price_diff: float | None = None
    has_anomaly: bool
    anomaly_details: list[AnomalyDetail]
    missing_suppliers: list[str]
    generated_at: str


class ComparisonGenerateResponse(BaseModel):
    """比价生成任务响应"""

    model_config = _CAMEL_CONFIG

    task_id: str


# ================================================================
# 导出
# ================================================================


class ExportRequest(BaseModel):
    """导出请求（可选参数）"""

    model_config = _CAMEL_CONFIG


class ExportResponse(BaseModel):
    """导出任务响应"""

    model_config = _CAMEL_CONFIG

    task_id: str


class ExportResult(BaseModel):
    """导出完成结果"""

    model_config = _CAMEL_CONFIG

    file_path: str
    file_name: str
    sheet_count: int


# ================================================================
# 问题清单
# ================================================================


class ProblemItem(BaseModel):
    """单个问题项"""

    model_config = _CAMEL_CONFIG

    id: str
    stage: str  # import / normalize / grouping / compliance / comparison
    target_id: str
    description: str
    severity: str = "warning"  # warning / error


class ProblemGroup(BaseModel):
    """问题分组"""

    model_config = _CAMEL_CONFIG

    type: str  # unconfirmed_supplier / unmapped_field / rule_conflict / ...
    label: str
    stage: str
    severity: str = "warning"  # warning / error
    count: int
    items: list[ProblemItem]
