from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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
    field: str
    patterns: list[str]
    replace_with: str = Field(..., alias="replaceWith")
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}


class RuleSet(BaseModel):
    """完整规则集（对应 JSON 文件结构）"""

    version: str = "1.0"
    last_updated: str = Field("", alias="lastUpdated")
    column_mapping_rules: list[ColumnMappingRule] = Field(
        default_factory=list, alias="columnMappingRules"
    )
    value_normalization_rules: list[ValueNormalizationRule] = Field(
        default_factory=list, alias="valueNormalizationRules"
    )

    model_config = {"populate_by_name": True}


class MatchResult(BaseModel):
    """单次规则匹配结果"""

    matched: bool
    target_field: str | None = Field(None, alias="targetField")
    matched_rule: ColumnMappingRule | None = Field(None, alias="matchedRule")
    conflicts: list[ColumnMappingRule] = Field(default_factory=list)
    resolution: str | None = None

    model_config = {"populate_by_name": True}


class RuleTestRequest(BaseModel):
    """规则测试请求"""

    column_name: str = Field(..., alias="columnName")
    project_id: str | None = Field(None, alias="projectId")

    model_config = {"populate_by_name": True}


class RuleTestResponse(BaseModel):
    """规则测试响应"""

    matched: bool
    target_field: str | None = Field(None, alias="targetField")
    matched_rule: dict | None = Field(None, alias="matchedRule")
    conflicts: list[dict] = Field(default_factory=list)
    resolution: str | None = None

    model_config = {"populate_by_name": True}


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

    model_config = {"populate_by_name": True}
