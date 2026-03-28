"""Tests for ProblemService (12 problem types) and the problems API endpoint."""
from __future__ import annotations

import json
import uuid

import pytest

from db.database import Database
from services.problem_service import ProblemService


# ---- helpers ----

def _insert_supplier_file(
    db: Database,
    *,
    sf_id: str = "sf1",
    project_id: str = "p1",
    supplier_name: str = "供应商A",
    supplier_confirmed: int = 0,
) -> None:
    with db.transaction() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO supplier_files
               (id, project_id, original_filename, file_path, file_type, supplier_name,
                supplier_confirmed, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sf_id, project_id, "test.xlsx", "/tmp/test.xlsx", "xlsx",
             supplier_name, supplier_confirmed, "2026-01-01T00:00:00Z"),
        )


def _insert_raw_table(db: Database, *, rt_id: str = "rt1", sf_id: str = "sf1") -> None:
    with db.transaction() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO raw_tables
               (id, supplier_file_id, table_index, sheet_name, row_count, column_count, raw_data, selected)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rt_id, sf_id, 0, "Sheet1", 1, 5, "[]", 1),
        )


def _insert_std_row(
    db: Database,
    *,
    row_id: str | None = None,
    rt_id: str = "rt1",
    sf_id: str = "sf1",
    product_name: str = "商品A",
    unit: str = "台",
    unit_price: float | None = 100.0,
    confidence: float = 1.0,
    needs_review: int = 0,
    is_manually_modified: int = 0,
    column_mapping: str | None = None,
    hit_rule_snapshots: str | None = None,
) -> str:
    rid = row_id or str(uuid.uuid4())
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO standardized_rows
               (id, raw_table_id, supplier_file_id, row_index, product_name,
                unit, unit_price, confidence, needs_review, is_manually_modified,
                column_mapping, hit_rule_snapshots, source_location)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, rt_id, sf_id, 0, product_name, unit, unit_price,
             confidence, needs_review, is_manually_modified,
             column_mapping, hit_rule_snapshots, "{}"),
        )
    return rid


def _insert_group(
    db: Database,
    *,
    group_id: str = "g1",
    project_id: str = "p1",
    group_name: str = "测试组",
    status: str = "candidate",
) -> None:
    with db.transaction() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO commodity_groups
               (id, project_id, group_name, normalized_key, confidence_level,
                match_score, match_reason, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, project_id, group_name, "test", "high", 1.0, "test", status),
        )


def _insert_comparison_result(
    db: Database,
    *,
    cr_id: str | None = None,
    group_id: str = "g1",
    project_id: str = "p1",
    has_anomaly: int = 1,
    anomaly_details: str = "[]",
) -> str:
    rid = cr_id or str(uuid.uuid4())
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO comparison_results
               (id, group_id, project_id, engine_versions, comparison_status,
                supplier_prices, min_price, has_anomaly, anomaly_details,
                missing_suppliers, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, group_id, project_id, "{}", "blocked", "[]", 100.0,
             has_anomaly, anomaly_details, "[]", "2026-01-01T00:00:00Z"),
        )
    return rid


def _insert_requirement(
    db: Database,
    *,
    req_id: str = "req1",
    project_id: str = "p1",
    title: str = "需求1",
    is_mandatory: int = 1,
) -> None:
    with db.transaction() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO requirement_items
               (id, project_id, title, match_type, is_mandatory, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (req_id, project_id, title, "keyword", is_mandatory, "2026-01-01T00:00:00Z"),
        )


def _insert_compliance_match(
    db: Database,
    *,
    cm_id: str | None = None,
    req_id: str = "req1",
    group_id: str = "g1",
    sf_id: str = "sf1",
    status: str = "unclear",
    needs_review: int = 1,
    is_acceptable: int = 0,
) -> str:
    cid = cm_id or str(uuid.uuid4())
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO compliance_matches
               (id, requirement_item_id, commodity_group_id, supplier_file_id,
                status, needs_review, is_acceptable)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cid, req_id, group_id, sf_id, status, needs_review, is_acceptable),
        )
    return cid


# ---- tests ----


class TestProblemServiceEmpty:
    """Empty project should return no problems."""

    def test_empty_project(self, project_db: Database) -> None:
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        assert problems == []


class TestUnconfirmedSuppliers:
    def test_unconfirmed_supplier_detected(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=0)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unconfirmed_supplier" in types

    def test_confirmed_supplier_not_detected(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unconfirmed_supplier" not in types


class TestUnmappedFields:
    def test_unmapped_field_detected(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        mapping = json.dumps({"unit_price": "报价", "unit": ""})
        _insert_std_row(project_db, column_mapping=mapping)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unmapped_field" in types

    def test_all_mapped_no_problem(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        mapping = json.dumps({"unit_price": "报价", "unit": "单位"})
        _insert_std_row(project_db, column_mapping=mapping)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unmapped_field" not in types


class TestRuleConflicts:
    def test_rule_conflict_detected(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        snapshots = json.dumps([
            {"target_field": "unit_price", "rule_id": "r1"},
            {"target_field": "unit_price", "rule_id": "r2"},
        ])
        _insert_std_row(project_db, hit_rule_snapshots=snapshots)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "rule_conflict" in types

    def test_no_conflict(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        snapshots = json.dumps([{"target_field": "unit_price", "rule_id": "r1"}])
        _insert_std_row(project_db, hit_rule_snapshots=snapshots)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "rule_conflict" not in types


class TestLowConfidence:
    def test_low_confidence_detected(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        _insert_std_row(project_db, confidence=0.5, needs_review=1, is_manually_modified=0)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "low_confidence_unconfirmed" in types

    def test_manually_modified_not_detected(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        _insert_std_row(project_db, confidence=0.5, needs_review=1, is_manually_modified=1)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "low_confidence_unconfirmed" not in types


class TestAnomalies:
    def test_unit_mismatch_detected(self, project_db: Database) -> None:
        _insert_group(project_db, status="confirmed")
        anomalies = json.dumps([{"type": "unit_mismatch", "description": "单位不一致"}])
        _insert_comparison_result(project_db, anomaly_details=anomalies)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unit_mismatch" in types

    def test_tax_basis_mismatch_detected(self, project_db: Database) -> None:
        _insert_group(project_db, status="confirmed")
        anomalies = json.dumps([{"type": "tax_basis_mismatch", "description": "税价口径不一致"}])
        _insert_comparison_result(project_db, anomaly_details=anomalies)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "tax_basis_mismatch" in types


class TestUnconfirmedGroups:
    def test_candidate_group_detected(self, project_db: Database) -> None:
        _insert_group(project_db, status="candidate")
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unconfirmed_group" in types

    def test_confirmed_group_not_detected(self, project_db: Database) -> None:
        _insert_group(project_db, status="confirmed")
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unconfirmed_group" not in types


class TestMissingRequiredFields:
    def test_missing_unit_price(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_raw_table(project_db)
        _insert_std_row(project_db, unit_price=None)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "missing_required_field" in types


class TestComplianceProblems:
    @pytest.fixture(autouse=True)
    def _setup(self, project_db: Database) -> None:
        _insert_supplier_file(project_db, supplier_confirmed=1)
        _insert_group(project_db, status="confirmed")
        _insert_requirement(project_db)

    def test_unconfirmed_compliance(self, project_db: Database) -> None:
        _insert_compliance_match(project_db, status="match", needs_review=1)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unconfirmed_compliance" in types

    def test_mandatory_not_met(self, project_db: Database) -> None:
        _insert_compliance_match(project_db, status="no_match", needs_review=0)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "mandatory_not_met" in types

    def test_unclear_unconfirmed(self, project_db: Database) -> None:
        _insert_compliance_match(project_db, status="unclear", needs_review=1)
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "unclear_unconfirmed" in types

    def test_partial_not_decided(self, project_db: Database) -> None:
        _insert_compliance_match(
            project_db, status="partial", needs_review=1, is_acceptable=0,
        )
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        types = [p.type for p in problems]
        assert "partial_not_decided" in types


class TestProblemGroupStructure:
    def test_count_matches_items(self, project_db: Database) -> None:
        _insert_group(project_db, group_id="g1", status="candidate")
        _insert_group(project_db, group_id="g2", status="candidate", group_name="测试组2")
        service = ProblemService(project_db)
        problems = service.get_problems("p1")
        for group in problems:
            assert group.count == len(group.items)
            for item in group.items:
                assert item.id
                assert item.stage
                assert item.target_id
                assert item.description
