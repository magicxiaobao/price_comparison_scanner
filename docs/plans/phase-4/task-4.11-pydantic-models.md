# Task 4.11: 符合性 + 比价相关 Pydantic 模型

## 输入条件

- Phase 3 完成（归组相关模型可参考）
- 技术架构 3.2 节数据库表结构已确定

## 输出物

- 创建: `backend/models/compliance.py`
- 创建: `backend/models/comparison.py`

## 禁止修改

- 不修改 `backend/models/project.py`
- 不修改 `backend/models/grouping.py`
- 不修改 `backend/db/schema.sql`
- 不修改 `frontend/`

## 实现规格

### models/compliance.py

```python
from pydantic import BaseModel, Field
from typing import Optional
from models.standardization import _CAMEL_CONFIG  # 统一 camelCase alias 策略

# ---- 需求标准 ----

class RequirementCreate(BaseModel):
    """创建需求项请求"""
    model_config = _CAMEL_CONFIG
    code: Optional[str] = None              # 需求编号，如 REQ-001，可自动生成
    category: str = Field(..., pattern=r"^(功能要求|技术规格|商务条款|服务要求|交付要求)$")
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    is_mandatory: bool = True
    match_type: str = Field(..., pattern=r"^(keyword|numeric|manual)$")
    expected_value: Optional[str] = None    # keyword: 关键词; numeric: 数值; manual: 说明
    operator: Optional[str] = Field(None, pattern=r"^(gte|lte|eq|range)$")  # 仅 numeric 类型

class RequirementUpdate(BaseModel):
    """更新需求项请求"""
    model_config = _CAMEL_CONFIG
    project_id: str                         # [C1-fix] API 层用于定位项目 DB
    code: Optional[str] = None
    category: Optional[str] = Field(None, pattern=r"^(功能要求|技术规格|商务条款|服务要求|交付要求)$")
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    is_mandatory: Optional[bool] = None
    match_type: Optional[str] = Field(None, pattern=r"^(keyword|numeric|manual)$")
    expected_value: Optional[str] = None
    operator: Optional[str] = Field(None, pattern=r"^(gte|lte|eq|range)$")

class RequirementResponse(BaseModel):
    """需求项响应"""
    model_config = _CAMEL_CONFIG
    id: str
    project_id: str
    code: Optional[str]
    category: str
    title: str
    description: Optional[str]
    is_mandatory: bool
    match_type: str
    expected_value: Optional[str]
    operator: Optional[str]
    sort_order: int
    created_at: str

class RequirementImportResult(BaseModel):
    """需求标准导入结果"""
    model_config = _CAMEL_CONFIG
    total: int
    imported: int
    skipped: int
    errors: list[str]

# ---- 符合性匹配 ----

class ComplianceMatchResponse(BaseModel):
    """单条符合性匹配结果"""
    model_config = _CAMEL_CONFIG
    id: str
    requirement_item_id: str
    commodity_group_id: str
    supplier_file_id: str
    supplier_name: str
    status: str                             # match / partial / no_match / unclear
    is_acceptable: bool
    match_score: Optional[float]
    evidence_text: Optional[str]
    evidence_location: Optional[str]        # JSON 字符串
    match_method: Optional[str]             # keyword / numeric / manual
    needs_review: bool
    confirmed_at: Optional[str]

class ComplianceConfirmRequest(BaseModel):
    """确认匹配结果请求"""
    model_config = _CAMEL_CONFIG
    project_id: str                         # [C2-fix] API 层用于定位项目 DB
    status: str = Field(..., pattern=r"^(match|partial|no_match|unclear)$")

class ComplianceAcceptRequest(BaseModel):
    """标记部分符合为可接受请求"""
    model_config = _CAMEL_CONFIG
    project_id: str                         # [C2-fix] API 层用于定位项目 DB
    is_acceptable: bool

class ComplianceMatrixCell(BaseModel):
    model_config = _CAMEL_CONFIG
    """符合性矩阵单元格"""
    match_id: str
    status: str
    is_acceptable: bool
    needs_review: bool
    evidence_text: Optional[str]

class ComplianceMatrixRow(BaseModel):
    """符合性矩阵一行（一个需求项）"""
    model_config = _CAMEL_CONFIG
    requirement: RequirementResponse
    suppliers: dict[str, ComplianceMatrixCell]   # key: supplier_file_id

class ComplianceMatrixResponse(BaseModel):
    """符合性矩阵完整响应"""
    model_config = _CAMEL_CONFIG
    supplier_names: dict[str, str]               # key: supplier_file_id, value: supplier_name
    rows: list[ComplianceMatrixRow]

class ComplianceEvaluateResponse(BaseModel):
    """符合性匹配任务响应"""
    model_config = _CAMEL_CONFIG
    task_id: str
```

### models/comparison.py

```python
from pydantic import BaseModel
from typing import Optional
from models.standardization import _CAMEL_CONFIG  # 统一 camelCase alias 策略

# ---- 供应商报价 ----

class SupplierPrice(BaseModel):
    """供应商报价（JSON 字段元素）"""
    model_config = _CAMEL_CONFIG
    supplier_file_id: str
    supplier_name: str
    unit_price: Optional[float]
    total_price: Optional[float]
    tax_basis: Optional[str] = None         # [C12-fix] 含税/不含税/未知 — ReportGenerator Sheet1 需要
    unit: Optional[str] = None              # [C12-fix] 单位 — ReportGenerator Sheet1 需要
    compliance_status: Optional[str] = None  # match / partial / no_match / unclear / None
    is_acceptable: Optional[bool] = None

# ---- 异常 ----

class AnomalyDetail(BaseModel):
    """异常详情（JSON 字段元素）"""
    model_config = _CAMEL_CONFIG
    type: str                                # tax_basis_mismatch / unit_mismatch / currency_mismatch / missing_required_field
    description: str
    blocking: bool                           # 是否阻断比价结论
    affected_suppliers: list[str]            # 涉及的供应商名

# ---- 比价结果 ----

class ComparisonResultResponse(BaseModel):
    """比价结果响应"""
    model_config = _CAMEL_CONFIG
    id: str
    group_id: str
    group_name: str
    project_id: str
    comparison_status: str                   # comparable / blocked / partial
    supplier_prices: list[SupplierPrice]
    min_price: Optional[float]
    effective_min_price: Optional[float]
    max_price: Optional[float]
    avg_price: Optional[float]
    price_diff: Optional[float]
    has_anomaly: bool
    anomaly_details: list[AnomalyDetail]
    missing_suppliers: list[str]
    generated_at: str

class ComparisonGenerateResponse(BaseModel):
    """比价生成任务响应"""
    model_config = _CAMEL_CONFIG
    task_id: str

# ---- 导出 ----

class ExportRequest(BaseModel):
    """导出请求（可选参数）"""
    model_config = _CAMEL_CONFIG
    pass  # MVP 无额外参数，直接导出

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

# ---- 问题清单 ----

class ProblemItem(BaseModel):
    """单个问题项"""
    model_config = _CAMEL_CONFIG
    id: str
    stage: str                               # import / normalize / grouping / compliance / comparison
    target_id: str                           # 关联的实体 ID
    description: str
    severity: str = "warning"                # warning / error

class ProblemGroup(BaseModel):
    """问题分组"""
    model_config = _CAMEL_CONFIG
    type: str                                # unconfirmed_supplier / unmapped_field / rule_conflict / ...
    label: str                               # 显示名称
    stage: str                               # 所属阶段
    severity: str = "warning"                # [M1-fix] warning / error — 默认 warning，mandatory_not_met 等为 error
    count: int
    items: list[ProblemItem]
```

## 测试与验收

```bash
cd backend
ruff check models/compliance.py models/comparison.py
mypy models/compliance.py models/comparison.py --ignore-missing-imports

# 模型可正确实例化
python -c "
from models.compliance import RequirementCreate, ComplianceMatchResponse, ComplianceMatrixResponse
from models.comparison import ComparisonResultResponse, ProblemGroup, SupplierPrice, AnomalyDetail

# RequirementCreate
r = RequirementCreate(category='技术规格', title='内存>=16GB', match_type='numeric', expected_value='16', operator='gte')
assert r.match_type == 'numeric'

# SupplierPrice
sp = SupplierPrice(supplier_file_id='sf1', supplier_name='供应商A', unit_price=4299.0, total_price=42990.0)
assert sp.unit_price == 4299.0

# AnomalyDetail
ad = AnomalyDetail(type='tax_basis_mismatch', description='税价口径不一致', blocking=True, affected_suppliers=['供应商A'])
assert ad.blocking is True

print('✓ 所有 Pydantic 模型实例化正常')
"
```

**断言清单：**
- `ruff check` → 退出码 0
- `mypy` → 退出码 0
- RequirementCreate 校验 category 枚举、match_type 枚举
- ComparisonResultResponse 包含 supplier_prices 列表、anomaly_details 列表
- ProblemGroup 包含 type, count, items

## 提交

```bash
git add backend/models/compliance.py backend/models/comparison.py
git commit -m "Phase 4.11: 符合性 + 比价 Pydantic 模型 — RequirementCreate/ComplianceMatch/ComparisonResult/Problem"
```
