from __future__ import annotations

import uuid

from db.compliance_repo import ComplianceRepo


class TestComplianceRepo:
    def _insert_requirement(self, project_db, req_id: str = "r1") -> None:  # type: ignore[no-untyped-def]
        """插入一条需求项作为外键依赖"""
        with project_db.transaction() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO requirement_items
                   (id, project_id, title, match_type, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (req_id, "p1", "test req", "keyword", 0, "2026-01-01T00:00:00Z"),
            )

    def _insert_group(self, project_db, group_id: str = "g1") -> None:  # type: ignore[no-untyped-def]
        """插入一个归组作为外键依赖"""
        with project_db.transaction() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO commodity_groups
                   (id, project_id, group_name, normalized_key,
                    confidence_level, match_score, match_reason, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (group_id, "p1", "test group", "test", "high", 0.9, "test", "confirmed"),
            )

    def _insert_supplier_file(self, project_db, sf_id: str = "sf1") -> None:  # type: ignore[no-untyped-def]
        """插入一个供应商文件作为外键依赖"""
        with project_db.transaction() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO supplier_files
                   (id, project_id, supplier_name, original_filename, file_path, file_type, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sf_id, "p1", "供应商A", "test.xlsx", "/tmp/test.xlsx", "xlsx", "2026-01-01T00:00:00Z"),
            )

    def test_insert_and_get(self, project_db) -> None:  # type: ignore[no-untyped-def]
        self._insert_requirement(project_db)
        self._insert_group(project_db)
        self._insert_supplier_file(project_db)

        repo = ComplianceRepo(project_db)
        mid = str(uuid.uuid4())
        repo.insert(
            match_id=mid, requirement_item_id="r1",
            commodity_group_id="g1", supplier_file_id="sf1",
            status="match", is_acceptable=False, match_score=1.0,
            evidence_text="找到关键词", evidence_location="{}",
            match_method="keyword", needs_review=False, engine_versions="{}",
        )
        row = repo.get_by_id(mid)
        assert row is not None
        assert row["status"] == "match"

    def test_update_status(self, project_db) -> None:  # type: ignore[no-untyped-def]
        self._insert_requirement(project_db)
        self._insert_group(project_db)
        self._insert_supplier_file(project_db)

        repo = ComplianceRepo(project_db)
        mid = str(uuid.uuid4())
        repo.insert(
            match_id=mid, requirement_item_id="r1",
            commodity_group_id="g1", supplier_file_id="sf1",
            status="unclear", is_acceptable=False, match_score=0.0,
            evidence_text="", evidence_location="{}",
            match_method="manual", needs_review=True, engine_versions="{}",
        )
        repo.update_status(mid, "match", confirmed_at="2026-01-01T00:00:00Z")
        row = repo.get_by_id(mid)
        assert row is not None
        assert row["status"] == "match"
        assert row["needs_review"] == 0

    def test_update_acceptable(self, project_db) -> None:  # type: ignore[no-untyped-def]
        self._insert_requirement(project_db)
        self._insert_group(project_db)
        self._insert_supplier_file(project_db)

        repo = ComplianceRepo(project_db)
        mid = str(uuid.uuid4())
        repo.insert(
            match_id=mid, requirement_item_id="r1",
            commodity_group_id="g1", supplier_file_id="sf1",
            status="partial", is_acceptable=False, match_score=0.5,
            evidence_text="", evidence_location="{}",
            match_method="keyword", needs_review=True, engine_versions="{}",
        )
        repo.update_acceptable(mid, True)
        row = repo.get_by_id(mid)
        assert row is not None
        assert row["is_acceptable"] == 1
