from __future__ import annotations

from pydantic import BaseModel, Field

from models.standardization import _CAMEL_CONFIG

# ================================================================
# 归组成员（对应 standardized_row 的摘要信息）
# ================================================================


class GroupMemberSummary(BaseModel):
    """归组成员摘要 — 展示在归组列表中的行信息"""

    model_config = _CAMEL_CONFIG

    standardized_row_id: str
    supplier_name: str
    product_name: str
    spec_model: str = ""
    unit: str = ""
    unit_price: float | None = None
    quantity: float | None = None
    confidence: float = 1.0


# ================================================================
# 归组响应模型
# ================================================================


class CommodityGroupResponse(BaseModel):
    """归组响应 — GET /api/projects/{project_id}/groups 的列表项"""

    model_config = _CAMEL_CONFIG

    id: str
    project_id: str
    group_name: str
    normalized_key: str
    confidence_level: str  # high / medium / low
    match_score: float
    match_reason: str
    status: str  # candidate / confirmed / split / not_comparable
    confirmed_at: str | None = None
    members: list[GroupMemberSummary] = Field(default_factory=list)
    member_count: int = 0


# ================================================================
# 归组操作请求模型
# ================================================================


class GroupingGenerateRequest(BaseModel):
    """生成归组候选 — POST /api/projects/{project_id}/grouping/generate"""

    pass


class GroupingGenerateResponse(BaseModel):
    """生成归组候选的异步任务响应"""

    model_config = _CAMEL_CONFIG

    task_id: str


class GroupConfirmResponse(BaseModel):
    """确认归组响应"""

    model_config = _CAMEL_CONFIG

    id: str
    status: str  # "confirmed"
    confirmed_at: str


class GroupSplitRequest(BaseModel):
    """拆分归组请求 — PUT /api/groups/{group_id}/split"""

    model_config = _CAMEL_CONFIG

    project_id: str
    new_groups: list[list[str]] = Field(
        ...,
        min_length=2,
        description="拆分后的新组，每组为 standardized_row_id 列表，至少拆为 2 组",
    )


class GroupSplitResponse(BaseModel):
    """拆分归组响应"""

    model_config = _CAMEL_CONFIG

    original_group_id: str
    new_groups: list[CommodityGroupResponse]


class GroupMergeRequest(BaseModel):
    """合并归组请求 — POST /api/projects/{project_id}/grouping/merge"""

    model_config = _CAMEL_CONFIG

    group_ids: list[str] = Field(
        ...,
        min_length=2,
        description="要合并的归组 ID 列表，至少 2 个",
    )


class GroupMergeResponse(BaseModel):
    """合并归组响应"""

    model_config = _CAMEL_CONFIG

    merged_group: CommodityGroupResponse
    removed_group_ids: list[str]


class GroupMarkNotComparableResponse(BaseModel):
    """标记不可比响应"""

    model_config = _CAMEL_CONFIG

    id: str
    status: str  # "not_comparable"


class GroupActionRequest(BaseModel):
    """归组操作通用请求（confirm / not-comparable 等需要 project_id 的操作）"""

    model_config = _CAMEL_CONFIG

    project_id: str


class GroupMoveMemberRequest(BaseModel):
    """成员移动请求"""

    model_config = _CAMEL_CONFIG

    project_id: str
    target_group_id: str
    row_id: str


class GroupMoveMemberResponse(BaseModel):
    """成员移动响应"""

    model_config = _CAMEL_CONFIG

    source_group: CommodityGroupResponse
    target_group: CommodityGroupResponse
    moved_row_id: str
