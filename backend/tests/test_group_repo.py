import uuid

from db.group_repo import GroupRepo


class TestGroupRepo:
    def test_insert_and_get(self, project_db):
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="thinkpad e14", normalized_key="thinkpad e14",
            confidence_level="high", engine_versions='{"grouper":"1.0"}',
            match_score=0.95, match_reason="名称一致",
        )
        group = repo.get_group_by_id(gid)
        assert group is not None
        assert group["group_name"] == "thinkpad e14"
        assert group["confidence_level"] == "high"
        assert group["status"] == "candidate"

    def test_add_and_get_members(self, project_db, sample_standardized_rows):
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        row_ids = [r["id"] for r in sample_standardized_rows[:2]]
        repo.add_members(gid, row_ids)
        members = repo.get_group_members(gid)
        assert len(members) == 2

    def test_list_groups_ordered(self, project_db):
        repo = GroupRepo(project_db)
        for level in ["low", "high", "medium"]:
            repo.insert_group(
                group_id=str(uuid.uuid4()), project_id="p1",
                group_name=f"group-{level}", normalized_key=f"group-{level}",
                confidence_level=level, engine_versions="{}",
                match_score=0.5, match_reason="test",
            )
        groups = repo.list_groups_by_project("p1")
        levels = [g["confidence_level"] for g in groups]
        assert levels == ["high", "medium", "low"]

    def test_update_status(self, project_db):
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        repo.update_status(gid, "confirmed", confirmed_at="2026-01-01T00:00:00Z")
        group = repo.get_group_by_id(gid)
        assert group is not None
        assert group["status"] == "confirmed"
        assert group["confirmed_at"] == "2026-01-01T00:00:00Z"

    def test_delete_group_cascades(self, project_db, sample_standardized_rows):
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        repo.add_members(gid, [sample_standardized_rows[0]["id"]])
        repo.delete_group(gid)
        assert repo.get_group_by_id(gid) is None
        members = repo.get_group_members(gid)
        assert len(members) == 0

    def test_delete_groups_by_project(self, project_db):
        repo = GroupRepo(project_db)
        for _ in range(3):
            repo.insert_group(
                group_id=str(uuid.uuid4()), project_id="p1",
                group_name="test", normalized_key="test",
                confidence_level="high", engine_versions="{}",
                match_score=0.9, match_reason="test",
            )
        count = repo.delete_groups_by_project("p1")
        assert count == 3
        assert repo.list_groups_by_project("p1") == []

    def test_remove_member(self, project_db, sample_standardized_rows):
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        row_ids = [r["id"] for r in sample_standardized_rows[:2]]
        repo.add_members(gid, row_ids)
        repo.remove_member(gid, row_ids[0])
        members = repo.get_group_members(gid)
        assert len(members) == 1
        assert members[0]["standardized_row_id"] == row_ids[1]
