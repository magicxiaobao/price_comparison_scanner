from datetime import UTC, datetime

from db.database import Database


class ComparisonRepo:
    """comparison_results 表操作 — 纯数据访问层"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        result_id: str,
        group_id: str,
        project_id: str,
        engine_versions: str,
        comparison_status: str,
        supplier_prices: str,
        min_price: float | None,
        effective_min_price: float | None,
        max_price: float | None,
        avg_price: float | None,
        price_diff: float | None,
        has_anomaly: bool,
        anomaly_details: str,
        missing_suppliers: str,
    ) -> dict:
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO comparison_results
                   (id, group_id, project_id, engine_versions, comparison_status,
                    supplier_prices, min_price, effective_min_price, max_price, avg_price,
                    price_diff, has_anomaly, anomaly_details, missing_suppliers, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result_id,
                    group_id,
                    project_id,
                    engine_versions,
                    comparison_status,
                    supplier_prices,
                    min_price,
                    effective_min_price,
                    max_price,
                    avg_price,
                    price_diff,
                    1 if has_anomaly else 0,
                    anomaly_details,
                    missing_suppliers,
                    now,
                ),
            )
        result = self.get_by_id(result_id)
        assert result is not None
        return result

    def get_by_id(self, result_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM comparison_results WHERE id = ?", (result_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM comparison_results WHERE project_id = ? ORDER BY generated_at DESC",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_by_project(self, project_id: str) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM comparison_results WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount
