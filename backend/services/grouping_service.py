import json
import uuid
from datetime import UTC, datetime

from db.database import Database
from db.group_repo import GroupRepo
from engines.commodity_grouper import CommodityGrouper
from models.grouping import (
    CommodityGroupResponse,
    GroupConfirmResponse,
    GroupMarkNotComparableResponse,
    GroupMemberSummary,
    GroupMergeResponse,
    GroupMoveMemberResponse,
    GroupSplitResponse,
)

ENGINE_VERSION = "commodity_grouper:1.0"


class GroupingService:
    """归组业务编排 — 协调 CommodityGrouper 引擎 + GroupRepo + 失效传播"""

    def __init__(self, db: Database):
        self.db = db
        self.repo = GroupRepo(db)
        self.engine = CommodityGrouper()

    def generate_candidates(self, progress_callback: object, project_id: str) -> list[CommodityGroupResponse]:
        """
        生成候选归组。

        1. 清除该项目已有归组
        2. 从 standardized_rows 查询所有已标准化的行
        3. 调用 CommodityGrouper.generate_candidates()
        4. 将结果写入 commodity_groups + group_members
        5. 更新项目阶段状态
        6. 返回归组列表
        """
        _progress = progress_callback  # type: ignore[assignment]

        # 清除旧归组
        self.repo.delete_groups_by_project(project_id)
        _progress(0.1)  # type: ignore[operator]

        # 查询标准化行
        rows = self._get_standardized_rows(project_id)
        if not rows:
            return []

        # 生成候选
        candidates = self.engine.generate_candidates(rows)
        _progress(0.5)  # type: ignore[operator]

        # 持久化
        result: list[CommodityGroupResponse] = []
        for candidate in candidates:
            group_id = str(uuid.uuid4())
            self.repo.insert_group(
                group_id=group_id,
                project_id=project_id,
                group_name=candidate.group_name,
                normalized_key=candidate.normalized_key,
                confidence_level=candidate.confidence_level,
                engine_versions=json.dumps({"grouper": ENGINE_VERSION}),
                match_score=candidate.match_score,
                match_reason=candidate.match_reason,
            )
            self.repo.add_members(group_id, candidate.member_row_ids)
            result.append(self._to_response(group_id, project_id))

        _progress(1.0)  # type: ignore[operator]

        # 更新阶段状态
        self._update_stage_status(project_id, "grouping_status", "completed")

        return result

    def list_groups(self, project_id: str) -> list[CommodityGroupResponse]:
        """获取项目所有归组"""
        groups = self.repo.list_groups_by_project(project_id)
        return [self._to_response(g["id"], project_id) for g in groups]

    def confirm_group(self, group_id: str) -> GroupConfirmResponse:
        """确认归组"""
        now = datetime.now(UTC).isoformat()
        self.repo.update_status(group_id, "confirmed", confirmed_at=now)

        group = self.repo.get_group_by_id(group_id)
        assert group is not None
        # 触发失效传播
        self._propagate_dirty(group["project_id"])

        return GroupConfirmResponse(id=group_id, status="confirmed", confirmed_at=now)

    def split_group(self, group_id: str, new_groups_row_ids: list[list[str]]) -> GroupSplitResponse:
        """
        拆分归组。

        1. 验证原组存在
        2. 删除原组
        3. 为每个子组创建新归组
        4. 触发失效传播
        """
        original = self.repo.get_group_by_id(group_id)
        if not original:
            raise ValueError(f"归组不存在: {group_id}")

        project_id = original["project_id"]

        # 删除原组
        self.repo.delete_group(group_id)

        # 创建新组
        new_responses: list[CommodityGroupResponse] = []
        for row_ids in new_groups_row_ids:
            new_id = str(uuid.uuid4())
            self.repo.insert_group(
                group_id=new_id,
                project_id=project_id,
                group_name=original["group_name"],
                normalized_key=original["normalized_key"],
                confidence_level="medium",  # 拆分后降为 medium
                engine_versions=original["engine_versions"],
                match_score=0.0,
                match_reason=f"从归组 {group_id[:8]} 拆分",
                status="candidate",
            )
            self.repo.add_members(new_id, row_ids)
            new_responses.append(self._to_response(new_id, project_id))

        # 触发失效传播
        self._propagate_dirty(project_id)

        return GroupSplitResponse(
            original_group_id=group_id,
            new_groups=new_responses,
        )

    def merge_groups(self, project_id: str, group_ids: list[str]) -> GroupMergeResponse:
        """
        合并归组。

        1. 收集所有成员 row_ids
        2. 取第一个组作为合并目标
        3. 删除所有组
        4. 创建合并后新组
        5. 触发失效传播
        """
        all_row_ids: list[str] = []
        first_group = None

        for gid in group_ids:
            group = self.repo.get_group_by_id(gid)
            if not group:
                raise ValueError(f"归组不存在: {gid}")
            members = self.repo.get_group_members(gid)
            all_row_ids.extend(m["standardized_row_id"] for m in members)
            if first_group is None:
                first_group = group

        assert first_group is not None

        # 删除所有组
        for gid in group_ids:
            self.repo.delete_group(gid)

        # 创建合并后的新组
        merged_id = str(uuid.uuid4())
        self.repo.insert_group(
            group_id=merged_id,
            project_id=project_id,
            group_name=first_group["group_name"],
            normalized_key=first_group["normalized_key"],
            confidence_level="medium",  # 手工合并默认 medium
            engine_versions=first_group["engine_versions"],
            match_score=0.0,
            match_reason=f"手工合并 {len(group_ids)} 个归组",
            status="candidate",
        )
        # 去重后添加成员
        unique_row_ids = list(dict.fromkeys(all_row_ids))
        self.repo.add_members(merged_id, unique_row_ids)

        # 触发失效传播
        self._propagate_dirty(project_id)

        return GroupMergeResponse(
            merged_group=self._to_response(merged_id, project_id),
            removed_group_ids=list(group_ids),
        )

    def mark_not_comparable(self, group_id: str) -> GroupMarkNotComparableResponse:
        """标记归组为不可比"""
        self.repo.update_status(group_id, "not_comparable")
        group = self.repo.get_group_by_id(group_id)
        assert group is not None
        self._propagate_dirty(group["project_id"])
        return GroupMarkNotComparableResponse(id=group_id, status="not_comparable")

    def move_member(self, source_group_id: str, target_group_id: str, row_id: str) -> GroupMoveMemberResponse:
        """
        原子操作：将成员从源组移动到目标组。
        """
        source = self.repo.get_group_by_id(source_group_id)
        target = self.repo.get_group_by_id(target_group_id)
        if not source or not target:
            raise ValueError("源组或目标组不存在")

        if target["status"] in ("confirmed", "not_comparable"):
            raise ValueError(f"目标组状态为 {target['status']}，不接受新成员")

        source_members = self.repo.get_group_members(source_group_id)
        if len(source_members) <= 1:
            raise ValueError("源组仅剩 1 个成员，不可移出")

        member_ids = [m["standardized_row_id"] for m in source_members]
        if row_id not in member_ids:
            raise ValueError(f"成员 {row_id} 不属于源组 {source_group_id}")

        # 原子移动
        self.repo.remove_member(source_group_id, row_id)
        self.repo.add_member(target_group_id, row_id)

        # 触发失效传播
        self._propagate_dirty(source["project_id"])

        return GroupMoveMemberResponse(
            source_group=self._to_response(source_group_id, source["project_id"]),
            target_group=self._to_response(target_group_id, target["project_id"]),
            moved_row_id=row_id,
        )

    # ---- 私有方法 ----

    def _get_standardized_rows(self, project_id: str) -> list[dict]:
        """查询项目所有标准化行"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.* FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ?""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _to_response(self, group_id: str, project_id: str) -> CommodityGroupResponse:
        """将数据库记录转换为响应模型"""
        group = self.repo.get_group_by_id(group_id)
        assert group is not None
        members_data = self.repo.get_group_members(group_id)

        members = [
            GroupMemberSummary(
                standardized_row_id=m["standardized_row_id"],
                supplier_name=m.get("supplier_name", ""),
                product_name=m.get("product_name", ""),
                spec_model=m.get("spec_model", ""),
                unit=m.get("unit", ""),
                unit_price=m.get("unit_price"),
                quantity=m.get("quantity"),
                confidence=m.get("confidence", 1.0),
            )
            for m in members_data
        ]

        return CommodityGroupResponse(
            id=group["id"],
            project_id=project_id,
            group_name=group["group_name"],
            normalized_key=group["normalized_key"],
            confidence_level=group["confidence_level"],
            match_score=group["match_score"],
            match_reason=group["match_reason"],
            status=group["status"],
            confirmed_at=group.get("confirmed_at"),
            members=members,
            member_count=len(members),
        )

    _VALID_STAGES = frozenset({
        "import_status", "normalize_status", "grouping_status",
        "compliance_status", "comparison_status",
    })

    def _update_stage_status(self, project_id: str, stage: str, status: str) -> None:
        """更新项目阶段状态"""
        if stage not in self._VALID_STAGES:
            raise ValueError(f"Invalid stage: {stage}")
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {stage} = ?, updated_at = ? WHERE id = ?",  # noqa: S608
                (status, datetime.now(UTC).isoformat(), project_id),
            )

    def _propagate_dirty(self, project_id: str) -> None:
        """
        失效传播：归组变更 -> compliance dirty -> comparison dirty
        """
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE projects
                   SET compliance_status = CASE
                         WHEN compliance_status = 'skipped' THEN 'skipped'
                         ELSE 'dirty'
                       END,
                       comparison_status = 'dirty',
                       updated_at = ?
                   WHERE id = ?""",
                (now, project_id),
            )
