from fastapi import APIRouter, HTTPException

from api.deps import get_project_db
from models.grouping import (
    CommodityGroupResponse,
    GroupActionRequest,
    GroupConfirmResponse,
    GroupingGenerateResponse,
    GroupMarkNotComparableResponse,
    GroupMergeRequest,
    GroupMergeResponse,
    GroupMoveMemberRequest,
    GroupMoveMemberResponse,
    GroupSplitRequest,
    GroupSplitResponse,
)
from services.grouping_service import GroupingService

router = APIRouter(tags=["商品归组"])


def _get_grouping_service(project_id: str) -> GroupingService:
    db = get_project_db(project_id)
    return GroupingService(db)


@router.post("/projects/{project_id}/grouping/generate", response_model=GroupingGenerateResponse)
async def generate_grouping(project_id: str) -> GroupingGenerateResponse:
    """生成归组候选（异步任务）"""
    from engines.task_manager import get_task_manager

    service = _get_grouping_service(project_id)
    tm = get_task_manager()
    task_id = tm.submit(
        "grouping",
        service.generate_candidates,
        project_id,
    )
    return GroupingGenerateResponse(task_id=task_id)


@router.get("/projects/{project_id}/groups", response_model=list[CommodityGroupResponse])
async def list_groups(project_id: str) -> list[CommodityGroupResponse]:
    """获取项目所有归组"""
    service = _get_grouping_service(project_id)
    return service.list_groups(project_id)


@router.put("/groups/{group_id}/confirm", response_model=GroupConfirmResponse)
async def confirm_group(group_id: str, body: GroupActionRequest) -> GroupConfirmResponse:
    """确认归组"""
    service = _get_grouping_service(body.project_id)
    group = service.repo.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="归组不存在")
    return service.confirm_group(group_id)


@router.put("/groups/{group_id}/split", response_model=GroupSplitResponse)
async def split_group(group_id: str, req: GroupSplitRequest) -> GroupSplitResponse:
    """拆分归组。请求体含 project_id + new_groups"""
    service = _get_grouping_service(req.project_id)
    group = service.repo.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="归组不存在")
    try:
        return service.split_group(group_id, req.new_groups)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/projects/{project_id}/grouping/merge", response_model=GroupMergeResponse)
async def merge_groups(project_id: str, req: GroupMergeRequest) -> GroupMergeResponse:
    """手工合并归组"""
    service = _get_grouping_service(project_id)
    try:
        return service.merge_groups(project_id, req.group_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/groups/{group_id}/not-comparable", response_model=GroupMarkNotComparableResponse)
async def mark_not_comparable(group_id: str, body: GroupActionRequest) -> GroupMarkNotComparableResponse:
    """标记归组为不可比"""
    service = _get_grouping_service(body.project_id)
    group = service.repo.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="归组不存在")
    return service.mark_not_comparable(group_id)


@router.put("/groups/{group_id}/move-member", response_model=GroupMoveMemberResponse)
async def move_member(group_id: str, req: GroupMoveMemberRequest) -> GroupMoveMemberResponse:
    """将成员从当前归组移动到目标归组（原子操作）"""
    service = _get_grouping_service(req.project_id)
    source = service.repo.get_group_by_id(group_id)
    if not source:
        raise HTTPException(status_code=404, detail="源归组不存在")
    try:
        return service.move_member(group_id, req.target_group_id, req.row_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
