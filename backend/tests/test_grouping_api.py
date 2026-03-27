import uuid

import pytest

from services.grouping_service import GroupingService


class TestGroupingService:
    """直接测试 GroupingService（不走 HTTP），覆盖核心业务逻辑"""

    def test_generate_candidates(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        progress_values: list[float] = []

        def progress_callback(p: float) -> None:
            progress_values.append(p)

        result = service.generate_candidates(progress_callback, "p1")
        assert isinstance(result, list)
        assert len(result) >= 1
        # 进度回调应被调用
        assert len(progress_values) >= 2

    def test_generate_empty_project(self, project_db):
        service = GroupingService(project_db)
        result = service.generate_candidates(lambda p: None, "p1")
        assert result == []

    def test_list_groups(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        # 先生成
        service.generate_candidates(lambda p: None, "p1")
        groups = service.list_groups("p1")
        assert isinstance(groups, list)
        for g in groups:
            assert g.confidence_level in ("high", "medium", "low")
            assert g.status in ("candidate", "confirmed", "split", "not_comparable")

    def test_confirm_group(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        # 手动插入一个归组
        gid = str(uuid.uuid4())
        service.repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        service.repo.add_members(gid, [r["id"] for r in sample_standardized_rows[:2]])

        result = service.confirm_group(gid)
        assert result.status == "confirmed"
        assert result.confirmed_at is not None

    def test_split_group(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        gid = str(uuid.uuid4())
        service.repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        row_ids = [r["id"] for r in sample_standardized_rows[:2]]
        service.repo.add_members(gid, row_ids)

        result = service.split_group(gid, [[row_ids[0]], [row_ids[1]]])
        assert result.original_group_id == gid
        assert len(result.new_groups) == 2

    def test_merge_groups(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        # 创建两个归组
        gid1 = str(uuid.uuid4())
        gid2 = str(uuid.uuid4())
        for gid in [gid1, gid2]:
            service.repo.insert_group(
                group_id=gid, project_id="p1",
                group_name="test", normalized_key="test",
                confidence_level="high", engine_versions="{}",
                match_score=0.9, match_reason="test",
            )
        service.repo.add_members(gid1, [sample_standardized_rows[0]["id"]])
        service.repo.add_members(gid2, [sample_standardized_rows[1]["id"]])

        result = service.merge_groups("p1", [gid1, gid2])
        assert len(result.merged_group.members) == 2
        assert set(result.removed_group_ids) == {gid1, gid2}

    def test_mark_not_comparable(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        gid = str(uuid.uuid4())
        service.repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        result = service.mark_not_comparable(gid)
        assert result.status == "not_comparable"

    def test_move_member(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        gid1 = str(uuid.uuid4())
        gid2 = str(uuid.uuid4())
        for gid in [gid1, gid2]:
            service.repo.insert_group(
                group_id=gid, project_id="p1",
                group_name="test", normalized_key="test",
                confidence_level="high", engine_versions="{}",
                match_score=0.9, match_reason="test",
            )
        row_ids = [r["id"] for r in sample_standardized_rows[:2]]
        service.repo.add_members(gid1, row_ids)
        service.repo.add_members(gid2, [sample_standardized_rows[2]["id"]])

        result = service.move_member(gid1, gid2, row_ids[0])
        assert result.moved_row_id == row_ids[0]
        # 源组应少一个成员
        assert len(result.source_group.members) == 1
        # 目标组应多一个成员
        assert len(result.target_group.members) == 2

    def test_move_member_fails_single_member(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        gid1 = str(uuid.uuid4())
        gid2 = str(uuid.uuid4())
        for gid in [gid1, gid2]:
            service.repo.insert_group(
                group_id=gid, project_id="p1",
                group_name="test", normalized_key="test",
                confidence_level="high", engine_versions="{}",
                match_score=0.9, match_reason="test",
            )
        service.repo.add_members(gid1, [sample_standardized_rows[0]["id"]])
        service.repo.add_members(gid2, [sample_standardized_rows[1]["id"]])

        with pytest.raises(ValueError, match="仅剩 1 个成员"):
            service.move_member(gid1, gid2, sample_standardized_rows[0]["id"])

    def test_move_member_fails_confirmed_target(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        gid1 = str(uuid.uuid4())
        gid2 = str(uuid.uuid4())
        for gid in [gid1, gid2]:
            service.repo.insert_group(
                group_id=gid, project_id="p1",
                group_name="test", normalized_key="test",
                confidence_level="high", engine_versions="{}",
                match_score=0.9, match_reason="test",
            )
        row_ids = [r["id"] for r in sample_standardized_rows[:2]]
        service.repo.add_members(gid1, row_ids)
        service.repo.add_members(gid2, [sample_standardized_rows[2]["id"]])
        # 确认目标组
        service.repo.update_status(gid2, "confirmed")

        with pytest.raises(ValueError, match="不接受新成员"):
            service.move_member(gid1, gid2, row_ids[0])

    def test_dirty_propagation_after_confirm(self, project_db, sample_standardized_rows):
        service = GroupingService(project_db)
        gid = str(uuid.uuid4())
        service.repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )

        service.confirm_group(gid)

        # 检查项目阶段状态
        with project_db.read() as conn:
            cursor = conn.execute("SELECT comparison_status FROM projects WHERE id = 'p1'")
            row = cursor.fetchone()
            assert row is not None
            assert dict(row)["comparison_status"] == "dirty"

    def test_nonexistent_group_split(self, project_db):
        service = GroupingService(project_db)
        with pytest.raises(ValueError, match="归组不存在"):
            service.split_group("nonexistent", [["r1"], ["r2"]])

    def test_nonexistent_group_merge(self, project_db):
        service = GroupingService(project_db)
        with pytest.raises(ValueError, match="归组不存在"):
            service.merge_groups("p1", ["nonexistent1", "nonexistent2"])
