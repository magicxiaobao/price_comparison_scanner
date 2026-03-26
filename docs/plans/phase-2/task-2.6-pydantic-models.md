# Task 2.6: 标准化相关 Pydantic 模型

## 输入条件

- Phase 1 完成（`models/project.py` 已存在）
- 技术架构 3.1 规则 JSON 结构、3.2 standardized_rows 表结构、source_location JSON 结构已确定

## 输出物

- 创建: `backend/models/rule.py`
- 创建: `backend/models/standardization.py`
- 修改: `backend/models/__init__.py`（导出新模型）

## 禁止修改

- 不修改 `models/project.py`
- 不修改 `db/schema.sql`
- 不修改 `frontend/`

## 实现规格

### models/rule.py

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class MatchMode(str, Enum):
    exact = "exact"
    fuzzy = "fuzzy"
    regex = "regex"

class RuleType(str, Enum):
    column_mapping = "column_mapping"
    value_normalization = "value_normalization"

class RuleSource(str, Enum):
    template = "template"
    global_user = "global"
    project = "project"

class ColumnMappingRule(BaseModel):
    """列名映射规则"""
    id: str
    enabled: bool = True
    type: RuleType = RuleType.column_mapping
    source_keywords: list[str] = Field(..., alias="sourceKeywords")
    target_field: str = Field(..., alias="targetField")
    match_mode: MatchMode = Field(MatchMode.exact, alias="matchMode")
    priority: int = 100
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}

class ValueNormalizationRule(BaseModel):
    """值标准化辅助规则"""
    id: str
    type: RuleType = RuleType.value_normalization
    field: str                       # 适用的标准字段名
    patterns: list[str]              # 需要替换的模式
    replace_with: str = Field(..., alias="replaceWith")
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}

class RuleSet(BaseModel):
    """完整规则集（对应 JSON 文件结构）"""
    version: str = "1.0"
    last_updated: str = Field("", alias="lastUpdated")
    column_mapping_rules: list[ColumnMappingRule] = Field(default_factory=list, alias="columnMappingRules")
    value_normalization_rules: list[ValueNormalizationRule] = Field(default_factory=list, alias="valueNormalizationRules")

    model_config = {"populate_by_name": True}

class MatchResult(BaseModel):
    """单次规则匹配结果"""
    matched: bool
    target_field: str | None = Field(None, alias="targetField")
    matched_rule: Optional[ColumnMappingRule] = Field(None, alias="matchedRule")
    conflicts: list[ColumnMappingRule] = Field(default_factory=list)
    resolution: str | None = None

class RuleTestRequest(BaseModel):
    """规则测试请求"""
    column_name: str = Field(..., alias="columnName")
    project_id: str | None = Field(None, alias="projectId")

class RuleTestResponse(BaseModel):
    """规则测试响应"""
    matched: bool
    target_field: str | None = Field(None, alias="targetField")
    matched_rule: Optional[dict] = Field(None, alias="matchedRule")
    conflicts: list[dict] = Field(default_factory=list)
    resolution: str | None = None

class RuleImportSummary(BaseModel):
    """规则导入汇总"""
    total: int
    added: int
    conflicts: int
    skipped: int

class RuleCreateUpdate(BaseModel):
    """新增/编辑规则请求"""
    type: RuleType
    source_keywords: list[str] | None = Field(None, alias="sourceKeywords")
    target_field: str | None = Field(None, alias="targetField")
    match_mode: MatchMode = Field(MatchMode.exact, alias="matchMode")
    priority: int = 100
    # value_normalization 专用
    field: str | None = None
    patterns: list[str] | None = None
    replace_with: str | None = Field(None, alias="replaceWith")

    model_config = {"populate_by_name": True}

class TemplateInfo(BaseModel):
    """模板信息"""
    id: str
    name: str
    description: str
    rule_count: int = Field(0, alias="ruleCount")
```

### models/standardization.py

```python
from pydantic import BaseModel, Field
from typing import Optional

class SourceLocationItem(BaseModel):
    """单个字段的来源定位"""
    type: str                        # xlsx / docx / pdf / pdf_ocr
    sheet: str | None = None         # Excel sheet 名
    cell: str | None = None          # Excel 单元格引用
    table_index: int | None = None   # Word/PDF 表格序号
    row: int | None = None
    col: int | None = None
    page: int | None = None          # PDF 页码
    extraction_mode: str | None = None  # structure / ocr
    ocr_confidence: float | None = None

# source_location 类型：key 为标准字段名，value 为 SourceLocationItem
SourceLocation = dict[str, SourceLocationItem]

class HitRuleSnapshot(BaseModel):
    """规则命中快照"""
    rule_id: str
    rule_name: str
    match_content: str               # 如 "报价→unit_price"
    match_mode: str                  # exact / fuzzy / regex

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
    tax_basis: str | None = None     # known_inclusive / known_exclusive / unknown

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
    hit_rule_snapshots: list[HitRuleSnapshot] | None = Field(None, alias="hitRuleSnapshots")
    confidence: float = 1.0
    is_manually_modified: bool = Field(False, alias="isManuallyModified")
    needs_review: bool = Field(False, alias="needsReview")
    tax_basis: str | None = Field(None, alias="taxBasis")

    model_config = {"populate_by_name": True}

class FieldModifyRequest(BaseModel):
    """手工修正请求"""
    field: str                       # 标准字段名
    new_value: str | float | None = Field(..., alias="newValue")

class FieldModifyResponse(BaseModel):
    """手工修正响应"""
    success: bool
    audit_log: dict = Field(..., alias="auditLog")
    dirty_stages: list[str] = Field(default_factory=list, alias="dirtyStages")

class StandardizeRequest(BaseModel):
    """标准化执行请求（异步）"""
    force: bool = False              # 是否强制重新标准化（覆盖已有结果）
```

**设计要点：**

- 所有 JSON 字段有对应 Pydantic model 作为 schema 约束，不允许各模块直接拼 JSON
- `SourceLocation` 为 `dict[str, SourceLocationItem]`，key 为标准字段名
- `HitRuleSnapshot` 记录规则命中快照，支持历史追溯
- 规则模型使用 `alias` 映射 camelCase（JSON 文件格式）和 snake_case（Python 内部）
- `model_config = {"populate_by_name": True}` 允许同时使用 alias 和字段名

## 测试与验收

**断言清单：**

- `ColumnMappingRule` 可从 camelCase JSON 正确反序列化
- `RuleSet` 可从完整规则 JSON 文件结构正确反序列化
- `SourceLocationItem` 各种类型（xlsx/docx/pdf/pdf_ocr）均可正确解析
- `StandardizedRowCreate` 必填字段缺失时抛出 ValidationError
- `FieldModifyRequest` 的 `field` 字段验证通过
- 所有模型的序列化输出使用 camelCase（通过 alias）

**门禁命令：**

```bash
cd backend
ruff check models/rule.py models/standardization.py
mypy models/rule.py models/standardization.py --ignore-missing-imports
pytest tests/test_pydantic_models.py -x -q   # 若有模型单元测试
```

## 提交

```bash
git add backend/models/rule.py backend/models/standardization.py backend/models/__init__.py
git commit -m "Phase 2.6: 标准化相关 Pydantic 模型 — Rule/RuleSet/StandardizedRow/SourceLocation"
```
