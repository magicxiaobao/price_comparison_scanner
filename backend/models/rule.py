from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


_CAMEL_CONFIG = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


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

    model_config = _CAMEL_CONFIG

    id: str
    enabled: bool = True
    type: RuleType = RuleType.column_mapping
    source_keywords: list[str]
    target_field: str
    match_mode: MatchMode = MatchMode.exact
    priority: int = 100
    created_at: str


class ValueNormalizationRule(BaseModel):
    """值标准化辅助规则"""

    model_config = _CAMEL_CONFIG

    id: str
    type: RuleType = RuleType.value_normalization
    field: str
    patterns: list[str]
    replace_with: str
    created_at: str


class RuleSet(BaseModel):
    """完整规则集（对应 JSON 文件结构）"""

    model_config = _CAMEL_CONFIG

    version: str = "1.0"
    last_updated: str = ""
    column_mapping_rules: list[ColumnMappingRule] = []
    value_normalization_rules: list[ValueNormalizationRule] = []


class MatchResult(BaseModel):
    """单次规则匹配结果"""

    model_config = _CAMEL_CONFIG

    matched: bool
    target_field: str | None = None
    matched_rule: ColumnMappingRule | None = None
    conflicts: list[ColumnMappingRule] = []
    resolution: str | None = None


class RuleTestRequest(BaseModel):
    """规则测试请求"""

    model_config = _CAMEL_CONFIG

    column_name: str
    project_id: str | None = None


class RuleTestResponse(BaseModel):
    """规则测试响应"""

    model_config = _CAMEL_CONFIG

    matched: bool
    target_field: str | None = None
    matched_rule: dict | None = None
    conflicts: list[dict] = []
    resolution: str | None = None


class RuleImportSummary(BaseModel):
    """规则导入汇总"""

    total: int
    added: int
    conflicts: int
    skipped: int


class RuleCreateUpdate(BaseModel):
    """新增/编辑规则请求"""

    model_config = _CAMEL_CONFIG

    type: RuleType
    source_keywords: list[str] | None = None
    target_field: str | None = None
    match_mode: MatchMode = MatchMode.exact
    priority: int = 100
    # value_normalization 专用
    field: str | None = None
    patterns: list[str] | None = None
    replace_with: str | None = None


class TemplateInfo(BaseModel):
    """模板信息"""

    model_config = _CAMEL_CONFIG

    id: str
    name: str
    description: str
    rule_count: int = 0
