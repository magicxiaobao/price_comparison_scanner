from __future__ import annotations

from datetime import datetime
from pathlib import Path

from db.database import Database
from engines.report_generator import ReportGenerator
from models.comparison import ExportResult


class ReportService:
    """导出业务编排"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.engine = ReportGenerator()

    def export_report(self, project_id: str, output_dir: str) -> ExportResult:
        """生成 Excel 审计底稿。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
        file_name = f"比价审计底稿_{timestamp}.xlsx"
        output_path = str(Path(output_dir) / file_name)

        comparison_results = self._get_comparison_results(project_id)
        standardized_rows = self._get_standardized_rows(project_id)
        traceability_data = self._get_traceability_data(project_id)
        supplier_names = self._get_supplier_names(project_id)

        compliance_matrix = None
        if self._has_requirements(project_id):
            compliance_matrix = self._get_compliance_matrix_data(project_id)

        self.engine.export_to_excel(
            output_path=output_path,
            comparison_results=comparison_results,
            standardized_rows=standardized_rows,
            traceability_data=traceability_data,
            compliance_matrix=compliance_matrix,
            supplier_names=supplier_names,
        )

        sheet_count = 4 if compliance_matrix else 3
        return ExportResult(file_path=output_path, file_name=file_name, sheet_count=sheet_count)

    # ---- 数据收集 ----

    def _get_comparison_results(self, project_id: str) -> list[dict]:
        from db.comparison_repo import ComparisonRepo

        repo = ComparisonRepo(self.db)
        results = repo.list_by_project(project_id)
        for r in results:
            group = self._get_group(r["group_id"])
            r["group_name"] = group.get("group_name", "") if group else ""
        return results

    def _get_standardized_rows(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sf.supplier_name
                   FROM standardized_rows sr
                   JOIN supplier_files sf ON sf.id = sr.supplier_file_id
                   WHERE sf.project_id = ?
                   ORDER BY sf.supplier_name""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_traceability_data(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sf.supplier_name,
                          sf.original_filename as source_file
                   FROM standardized_rows sr
                   JOIN supplier_files sf ON sf.id = sr.supplier_file_id
                   WHERE sf.project_id = ?""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_supplier_names(self, project_id: str) -> dict[str, str]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT id, supplier_name FROM supplier_files WHERE project_id = ?",
                (project_id,),
            )
            return {row["id"]: row["supplier_name"] for row in cursor.fetchall()}

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

    def _get_compliance_matrix_data(self, project_id: str) -> dict:
        from services.compliance_service import ComplianceService

        service = ComplianceService(self.db)
        matrix = service.get_matrix(project_id)
        return matrix.model_dump()

    def _get_group(self, group_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM commodity_groups WHERE id = ?", (group_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
