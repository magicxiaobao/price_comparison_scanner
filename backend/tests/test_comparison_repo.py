import uuid

import pytest

from db.comparison_repo import ComparisonRepo


@pytest.fixture()
def _seed_group(project_db) -> None:  # type: ignore[no-untyped-def]
    """Insert a commodity_groups row so FK constraints are satisfied."""
    with project_db.transaction() as conn:
        conn.execute(
            """INSERT INTO commodity_groups
               (id, project_id, group_name, normalized_key, confidence_level, match_score, match_reason, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("g1", "p1", "test-group", "test", "high", 1.0, "test", "confirmed"),
        )


@pytest.mark.usefixtures("_seed_group")
class TestComparisonRepo:
    def test_insert_and_get(self, project_db) -> None:  # type: ignore[no-untyped-def]
        repo = ComparisonRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            result_id=rid,
            group_id="g1",
            project_id="p1",
            engine_versions="{}",
            comparison_status="comparable",
            supplier_prices="[]",
            min_price=100.0,
            effective_min_price=100.0,
            max_price=200.0,
            avg_price=150.0,
            price_diff=100.0,
            has_anomaly=False,
            anomaly_details="[]",
            missing_suppliers="[]",
        )
        row = repo.get_by_id(rid)
        assert row is not None
        assert row["min_price"] == 100.0
        assert row["comparison_status"] == "comparable"

    def test_list_by_project(self, project_db) -> None:  # type: ignore[no-untyped-def]
        repo = ComparisonRepo(project_db)
        for _ in range(3):
            repo.insert(
                result_id=str(uuid.uuid4()),
                group_id="g1",
                project_id="p1",
                engine_versions="{}",
                comparison_status="comparable",
                supplier_prices="[]",
                min_price=100.0,
                effective_min_price=100.0,
                max_price=200.0,
                avg_price=150.0,
                price_diff=100.0,
                has_anomaly=False,
                anomaly_details="[]",
                missing_suppliers="[]",
            )
        rows = repo.list_by_project("p1")
        assert len(rows) == 3

    def test_delete_by_project(self, project_db) -> None:  # type: ignore[no-untyped-def]
        repo = ComparisonRepo(project_db)
        repo.insert(
            result_id=str(uuid.uuid4()),
            group_id="g1",
            project_id="p1",
            engine_versions="{}",
            comparison_status="comparable",
            supplier_prices="[]",
            min_price=100.0,
            effective_min_price=100.0,
            max_price=200.0,
            avg_price=150.0,
            price_diff=100.0,
            has_anomaly=False,
            anomaly_details="[]",
            missing_suppliers="[]",
        )
        count = repo.delete_by_project("p1")
        assert count == 1
        assert repo.list_by_project("p1") == []

    def test_get_nonexistent(self, project_db) -> None:  # type: ignore[no-untyped-def]
        repo = ComparisonRepo(project_db)
        assert repo.get_by_id("nonexistent") is None
