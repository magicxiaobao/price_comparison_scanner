# Task 3.4: 归组相关 Pydantic 模型

## 输入条件

- Phase 2 完成（`models/` 目录已有 project.py 等模型文件）
- 数据库 schema 中 `commodity_groups` 和 `group_members` 表结构已定义

## 输出物

- 创建: `backend/models/grouping.py`

## 禁止修改

- 不修改 `backend/models/project.py`
- 不修改 `backend/db/`
- 不修改 `backend/api/`
- 不修改 `backend/services/`
- 不修改 `backend/engines/`
- 不修改 `frontend/`

## 实现规格

### models/grouping.py

```python
from pydantic import BaseModel, Field
from typing import Optional


# ================================================================
# 归组成员（对应 standardized_row 的摘要信息）
# ================================================================

class GroupMemberSummary(BaseModel):
    """归组成员摘要 — 展示在归组列表中的行信息"""
    standardized_row_id: str
    supplier_name: str             # 供应商名称（从 supplier_files 关联）
    product_name: str              # 原始商品名称
    spec: str = ""                 # 原始规格型号
    unit: str = ""                 # 单位
    unit_price: Optional[float] = None
    quantity: Optional[float] = None
    confidence: float = 1.0        # 标准化置信度


# ================================================================
# 归组响应模型
# ================================================================

class CommodityGroupResponse(BaseModel):
    """归组响应 — GET /api/projects/{id}/groups 的列表项"""
    id: str
    project_id: str
    group_name: str                # 归组显示名称
    normalized_key: str            # 归一化匹配键
    confidence_level: str          # high / medium / low
    match_score: float             # 多因子综合得分
    match_reason: str              # 可读归组理由
    status: str                    # candidate / confirmed / split / not_comparable
    confirmed_at: Optional[str] = None
    members: list[GroupMemberSummary] = Field(default_factory=list)
    member_count: int = 0          # 成员数量（冗余字段，方便前端展示）


# ================================================================
# 归组操作请求模型
# ================================================================

class GroupingGenerateRequest(BaseModel):
    """生成归组候选 — POST /api/projects/{id}/grouping/generate"""
    # MVP 无额外参数，保留扩展性
    pass


class GroupingGenerateResponse(BaseModel):
    """生成归组候选的异步任务响应"""
    task_id: str


class GroupConfirmResponse(BaseModel):
    """确认归组响应"""
    id: str
    status: str  # "confirmed"
    confirmed_at: str


class GroupSplitRequest(BaseModel):
    """拆分归组请求 — PUT /api/groups/{id}/split

    将一个归组拆分为多个新组。new_groups 中每个元素是一组 standardized_row_id。
    """
    project_id: str = Field(..., alias="projectId")
    new_groups: list[list[str]] = Field(
        ...,
        min_length=2,
        description="拆分后的新组，每组为 standardized_row_id 列表，至少拆为 2 组",
    )

    model_config = {"populate_by_name": True}


class GroupSplitResponse(BaseModel):
    """拆分归组响应"""
    original_group_id: str
    new_groups: list[CommodityGroupResponse]


class GroupMergeRequest(BaseModel):
    """合并归组请求 — POST /api/projects/{id}/grouping/merge

    将多个归组合并为一个。
    """
    group_ids: list[str] = Field(
        ...,
        min_length=2,
        description="要合并的归组 ID 列表，至少 2 个",
    )


class GroupMergeResponse(BaseModel):
    """合并归组响应"""
    merged_group: CommodityGroupResponse
    removed_group_ids: list[str]


class GroupMarkNotComparableResponse(BaseModel):
    """标记不可比响应"""
    id: str
    status: str  # "not_comparable"


class GroupActionRequest(BaseModel):
    """归组操作通用请求（confirm / not-comparable 等需要 project_id 的操作）"""
    project_id: str = Field(..., alias="projectId")

    model_config = {"populate_by_name": True}


class GroupMoveMemberRequest(BaseModel):
    """成员移动请求"""
    project_id: str = Field(..., alias="projectId")
    target_group_id: str = Field(..., alias="targetGroupId")
    row_id: str = Field(..., alias="rowId")

    model_config = {"populate_by_name": True}


class GroupMoveMemberResponse(BaseModel):
    """成员移动响应"""
    source_group: CommodityGroupResponse = Field(..., alias="sourceGroup")
    target_group: CommodityGroupResponse = Field(..., alias="targetGroup")
    moved_row_id: str = Field(..., alias="movedRowId")

    model_config = {"populate_by_name": True}
```

**设计要点：**

- `CommodityGroupResponse` 嵌套 `members` 列表，前端可直接展示每个归组的成员详情
- `member_count` 为冗余字段，避免前端需要 `members.length` 计算
- `GroupSplitRequest.new_groups` 要求至少 2 组（拆分至少产生 2 个新组）
- `GroupMergeRequest.group_ids` 要求至少 2 个（合并至少需要 2 个源组）
- 所有请求/响应模型与技术架构 5.1 节 API 路由对应
- `GroupMemberSummary` 包含 `supplier_name`，需要在 service 层通过 JOIN 获取

## 测试与验收

### 门禁命令

```bash
cd backend
ruff check models/grouping.py
mypy models/grouping.py --ignore-missing-imports
python -c "
from models.grouping import (
    GroupMemberSummary, CommodityGroupResponse,
    GroupingGenerateRequest, GroupingGenerateResponse,
    GroupConfirmResponse,
    GroupSplitRequest, GroupSplitResponse,
    GroupMergeRequest, GroupMergeResponse,
    GroupMarkNotComparableResponse,
)
# 验证模型可实例化
member = GroupMemberSummary(
    standardized_row_id='r1',
    supplier_name='供应商A',
    product_name='ThinkPad E14',
    spec='i5/16G',
    unit='台',
)
group = CommodityGroupResponse(
    id='g1', project_id='p1',
    group_name='thinkpad e14', normalized_key='thinkpad e14',
    confidence_level='high', match_score=0.95,
    match_reason='名称一致', status='candidate',
    members=[member], member_count=1,
)
assert group.confidence_level == 'high'

# 验证约束
import pydantic
try:
    GroupSplitRequest(new_groups=[['r1']])  # 少于 2 组
    assert False, 'Should have raised validation error'
except pydantic.ValidationError:
    pass

try:
    GroupMergeRequest(group_ids=['g1'])  # 少于 2 个
    assert False, 'Should have raised validation error'
except pydantic.ValidationError:
    pass

print('✓ 所有 Pydantic 模型验证通过')
"
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| `GroupMemberSummary` 可实例化 | 成功 |
| `CommodityGroupResponse` 含 `members` 列表 | 成功 |
| `GroupSplitRequest(new_groups=[["r1"]])` | 抛出 ValidationError（< 2 组） |
| `GroupMergeRequest(group_ids=["g1"])` | 抛出 ValidationError（< 2 个） |
| ruff check | exit 0 |
| mypy check | exit 0 |

## 提交

```bash
git add backend/models/grouping.py
git commit -m "Phase 3.4: 归组相关 Pydantic 模型 — 请求/响应/成员摘要"
```
