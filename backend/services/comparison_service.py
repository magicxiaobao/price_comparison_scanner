import json
import uuid
from datetime import UTC, datetime

from db.comparison_repo import ComparisonRepo
from db.database import Database
from engines.price_comparator import PriceComparator
from models.comparison import AnomalyDetail, ComparisonResultResponse, SupplierPrice


class ComparisonService:
    """比价业务编排"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.repo = ComparisonRepo(db)
        self.engine = PriceComparator()

    def generate_comparison(
        self, project_id: str
    ) -> list[ComparisonResultResponse]:
        """
        生成比价结果。

        1. 清除旧结果
        2. 获取已确认归组
        3. 检查是否有需求标准（决定是否传入 eligible_supplier_ids）
        4. 对每个组调用 PriceComparator
        5. 持久化
        6. 更新阶段状态
        """
        self.repo.delete_by_project(project_id)

        groups = self._get_confirmed_groups(project_id)
        has_requirements = self._has_requirements(project_id)

        results: list[ComparisonResultResponse] = []
        for group in groups:
            supplier_rows_map = self._get_supplier_rows_for_group(group["id"])

            eligible_ids: list[str] | None = None
            if has_requirements:
                eligible_ids = self._get_eligible_supplier_ids(group["id"])

            comparison = self.engine.compare_group(
                group, supplier_rows_map, eligible_ids
            )

            result_id = str(uuid.uuid4())
            # [C12-fix] 序列化时必须包含 tax_basis 和 unit
            supplier_prices_json = json.dumps(
                [
                    {
                        "supplier_file_id": p.supplier_file_id,
                        "supplier_name": p.supplier_name,
                        "unit_price": p.unit_price,
                        "total_price": p.total_price,
                        "tax_basis": p.tax_basis,
                        "unit": p.unit,
                    }
                    for p in comparison.supplier_prices
                ],
                ensure_ascii=False,
            )

            anomaly_json = json.dumps(
                [
                    {
                        "type": a.type,
                        "description": a.description,
                        "blocking": a.blocking,
                        "affected_suppliers": a.affected_suppliers,
                    }
                    for a in comparison.anomaly_details
                ],
                ensure_ascii=False,
            )

            missing_json = json.dumps(
                comparison.missing_suppliers, ensure_ascii=False
            )

            self.repo.insert(
                result_id=result_id,
                group_id=group["id"],
                project_id=project_id,
                engine_versions=json.dumps(
                    {"comparator": self.engine.ENGINE_VERSION}
                ),
                comparison_status=comparison.comparison_status,
                supplier_prices=supplier_prices_json,
                min_price=comparison.min_price,
                effective_min_price=comparison.effective_min_price,
                max_price=comparison.max_price,
                avg_price=comparison.avg_price,
                price_diff=comparison.price_diff,
                has_anomaly=comparison.has_anomaly,
                anomaly_details=anomaly_json,
                missing_suppliers=missing_json,
            )

            db_row = self.repo.get_by_id(result_id)
            assert db_row is not None
            results.append(self._to_response(db_row, group))

        self._update_stage_status(project_id, "comparison_status", "completed")
        return results

    def list_results(
        self, project_id: str
    ) -> list[ComparisonResultResponse]:
        rows = self.repo.list_by_project(project_id)
        results: list[ComparisonResultResponse] = []
        for row in rows:
            group = self._get_group(row["group_id"])
            if group:
                results.append(self._to_response(row, group))
        return results

    # ---- 私有方法 ----

    def _get_confirmed_groups(self, project_id: str) -> list[dict]:
        """[M4] 只查 confirmed 状态，不包含 candidate"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM commodity_groups
                   WHERE project_id = ? AND status = 'confirmed'""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_group(self, group_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM commodity_groups WHERE id = ?", (group_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def _get_supplier_rows_for_group(
        self, group_id: str
    ) -> dict[str, list[dict]]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sf.id as supplier_file_id, sf.supplier_name
                   FROM group_members gm
                   JOIN standardized_rows sr ON sr.id = gm.standardized_row_id
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE gm.group_id = ?""",
                (group_id,),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        result: dict[str, list[dict]] = {}
        for row in rows:
            sid = row["supplier_file_id"]
            result.setdefault(sid, []).append(row)
        return result

    def _has_requirements(self, project_id: str) -> bool:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            count: int = row[0]
            return count > 0

    def _get_eligible_supplier_ids(self, group_id: str) -> list[str]:
        from db.compliance_repo import ComplianceRepo

        result: list[str] = ComplianceRepo(self.db).get_eligible_supplier_ids(group_id)
        return result

    def _update_stage_status(
        self, project_id: str, stage: str, status: str
    ) -> None:
        allowed_stages = {
            "comparison_status",
            "compliance_status",
        }
        if stage not in allowed_stages:
            msg = f"Invalid stage: {stage}"
            raise ValueError(msg)
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {stage} = ?, updated_at = ? WHERE id = ?",  # noqa: S608
                (status, now, project_id),
            )

    def _to_response(
        self, row: dict, group: dict
    ) -> ComparisonResultResponse:
        supplier_prices = json.loads(row.get("supplier_prices", "[]"))
        anomaly_details = json.loads(row.get("anomaly_details", "[]"))
        missing = json.loads(row.get("missing_suppliers", "[]"))

        return ComparisonResultResponse(
            id=row["id"],
            group_id=row["group_id"],
            group_name=group.get("group_name", ""),
            project_id=row["project_id"],
            comparison_status=row["comparison_status"],
            supplier_prices=[SupplierPrice(**sp) for sp in supplier_prices],
            min_price=row.get("min_price"),
            effective_min_price=row.get("effective_min_price"),
            max_price=row.get("max_price"),
            avg_price=row.get("avg_price"),
            price_diff=row.get("price_diff"),
            has_anomaly=bool(row.get("has_anomaly", 0)),
            anomaly_details=[AnomalyDetail(**ad) for ad in anomaly_details],
            missing_suppliers=missing,
            generated_at=row["generated_at"],
        )
