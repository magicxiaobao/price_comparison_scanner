from __future__ import annotations

import uuid

import pytest

from db.requirement_repo import RequirementRepo


class TestRequirementRepo:
    def test_insert_and_get(self, project_db):
        repo = RequirementRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            req_id=rid, project_id="p1", code="REQ-001",
            category="技术规格", title="内存>=16GB", description="内存不低于16GB",
            is_mandatory=True, match_type="numeric",
            expected_value="16", operator="gte", sort_order=1,
        )
        row = repo.get_by_id(rid)
        assert row is not None
        assert row["title"] == "内存>=16GB"
        assert row["match_type"] == "numeric"
        assert row["is_mandatory"] == 1

    def test_list_by_project_ordered(self, project_db):
        repo = RequirementRepo(project_db)
        for i in range(3):
            repo.insert(
                req_id=str(uuid.uuid4()), project_id="p1",
                code=f"REQ-{i + 1:03d}", category="功能要求",
                title=f"需求{i + 1}", description=None,
                is_mandatory=True, match_type="keyword",
                expected_value=None, operator=None, sort_order=i,
            )
        rows = repo.list_by_project("p1")
        assert len(rows) == 3
        assert rows[0]["code"] == "REQ-001"

    def test_update(self, project_db):
        repo = RequirementRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            req_id=rid, project_id="p1", code="REQ-001",
            category="功能要求", title="原标题", description=None,
            is_mandatory=True, match_type="keyword",
            expected_value=None, operator=None, sort_order=0,
        )
        repo.update(rid, {"title": "新标题", "is_mandatory": 0})
        row = repo.get_by_id(rid)
        assert row is not None
        assert row["title"] == "新标题"
        assert row["is_mandatory"] == 0

    def test_delete(self, project_db):
        repo = RequirementRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            req_id=rid, project_id="p1", code="REQ-001",
            category="功能要求", title="删除测试", description=None,
            is_mandatory=True, match_type="manual",
            expected_value=None, operator=None, sort_order=0,
        )
        assert repo.delete(rid) is True
        assert repo.get_by_id(rid) is None

    def test_count_by_project(self, project_db):
        repo = RequirementRepo(project_db)
        assert repo.count_by_project("p1") == 0
        repo.insert(
            req_id=str(uuid.uuid4()), project_id="p1", code="REQ-001",
            category="功能要求", title="test", description=None,
            is_mandatory=True, match_type="keyword",
            expected_value=None, operator=None, sort_order=0,
        )
        assert repo.count_by_project("p1") == 1

    def test_get_max_sort_order(self, project_db):
        repo = RequirementRepo(project_db)
        assert repo.get_max_sort_order("p1") == 0
        repo.insert(
            req_id=str(uuid.uuid4()), project_id="p1", code="REQ-001",
            category="功能要求", title="test", description=None,
            is_mandatory=True, match_type="keyword",
            expected_value=None, operator=None, sort_order=5,
        )
        assert repo.get_max_sort_order("p1") == 5

    def test_delete_all_by_project(self, project_db):
        repo = RequirementRepo(project_db)
        for i in range(3):
            repo.insert(
                req_id=str(uuid.uuid4()), project_id="p1",
                code=f"REQ-{i + 1:03d}", category="功能要求",
                title=f"需求{i + 1}", description=None,
                is_mandatory=True, match_type="manual",
                expected_value=None, operator=None, sort_order=i,
            )
        deleted = repo.delete_all_by_project("p1")
        assert deleted == 3
        assert repo.count_by_project("p1") == 0
