from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from db.compliance_repo import ComplianceRepo
from db.database import Database
from db.requirement_repo import RequirementRepo
from engines.compliance_evaluator import ComplianceEvaluator
from models.compliance import (
    ComplianceMatrixCell,
    ComplianceMatrixResponse,
    ComplianceMatrixRow,
    RequirementCreate,
    RequirementImportResult,
    RequirementResponse,
    RequirementUpdate,
)


class ComplianceService:
    """符合性业务编排 — 协调 ComplianceEvaluator + RequirementRepo + 失效传播"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.repo = RequirementRepo(db)
        self.compliance_repo = ComplianceRepo(db)
        self.engine = ComplianceEvaluator()

    # ---- 需求标准 CRUD ----

    def create_requirement(
        self, project_id: str, req: RequirementCreate
    ) -> RequirementResponse:
        req_id = str(uuid.uuid4())
        sort_order = self.repo.get_max_sort_order(project_id) + 1
        code = req.code or self._generate_code(project_id)

        row = self.repo.insert(
            req_id=req_id,
            project_id=project_id,
            code=code,
            category=req.category,
            title=req.title,
            description=req.description,
            is_mandatory=req.is_mandatory,
            match_type=req.match_type,
            expected_value=req.expected_value,
            operator=req.operator,
            sort_order=sort_order,
        )

        self._activate_compliance_stage(project_id)
        self._propagate_dirty(project_id)

        return self._to_response(row)

    def list_requirements(self, project_id: str) -> list[RequirementResponse]:
        rows = self.repo.list_by_project(project_id)
        return [self._to_response(r) for r in rows]

    def update_requirement(
        self, req_id: str, req: RequirementUpdate
    ) -> RequirementResponse:
        updates = req.model_dump(exclude_unset=True)
        # project_id 仅用于定位 DB，不作为更新字段
        updates.pop("project_id", None)
        if "is_mandatory" in updates:
            updates["is_mandatory"] = 1 if updates["is_mandatory"] else 0
        row = self.repo.update(req_id, updates)
        if not row:
            raise ValueError(f"需求项不存在: {req_id}")

        self._propagate_dirty(row["project_id"])
        return self._to_response(row)

    def delete_requirement(self, req_id: str) -> bool:
        row = self.repo.get_by_id(req_id)
        if not row:
            return False
        project_id = row["project_id"]
        self.repo.delete(req_id)

        if self.repo.count_by_project(project_id) == 0:
            self._deactivate_compliance_stage(project_id)
        else:
            self._propagate_dirty(project_id)

        return True

    # ---- 导入导出 ----

    def import_requirements(
        self, project_id: str, file_path: str
    ) -> RequirementImportResult:
        parsed = self.engine.parse_requirements_excel(file_path)
        imported = 0
        skipped = 0
        errors: list[str] = []

        for item in parsed:
            try:
                req_id = str(uuid.uuid4())
                sort_order = self.repo.get_max_sort_order(project_id) + 1
                code = item.code or self._generate_code(project_id)
                self.repo.insert(
                    req_id=req_id,
                    project_id=project_id,
                    code=code,
                    category=item.category,
                    title=item.title,
                    description=item.description,
                    is_mandatory=item.is_mandatory,
                    match_type=item.match_type,
                    expected_value=item.expected_value,
                    operator=item.operator,
                    sort_order=sort_order,
                )
                imported += 1
            except Exception as e:
                errors.append(f"行 {item.title}: {e}")
                skipped += 1

        if imported > 0:
            self._activate_compliance_stage(project_id)
            self._propagate_dirty(project_id)

        return RequirementImportResult(
            total=len(parsed), imported=imported, skipped=skipped, errors=errors
        )

    def export_requirements(self, project_id: str, output_path: str) -> str:
        # [M3] 确保导出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        rows = self.repo.list_by_project(project_id)
        return self.engine.export_requirements_template(rows, output_path)

    # ---- 符合性匹配 ----

    def evaluate(self, project_id: str) -> list[str]:
        """执行符合性匹配：清除旧结果 → 遍历已确认归组 × 供应商 × 需求项 → 持久化。"""
        self.compliance_repo.delete_by_project(project_id)

        requirements = self.repo.list_by_project(project_id)
        if not requirements:
            return []

        # [M4] 仅对 confirmed 状态的归组执行匹配
        groups = self._get_confirmed_groups(project_id)
        results: list[str] = []

        for group in groups:
            supplier_rows_map = self._get_supplier_rows_for_group(group["id"])
            for supplier_file_id, rows in supplier_rows_map.items():
                for req in requirements:
                    match_result = self.engine.evaluate_single(
                        req, rows, supplier_file_id
                    )
                    match_id = str(uuid.uuid4())
                    self.compliance_repo.insert(
                        match_id=match_id,
                        requirement_item_id=req["id"],
                        commodity_group_id=group["id"],
                        supplier_file_id=supplier_file_id,
                        status=match_result.status,
                        is_acceptable=False,
                        match_score=match_result.match_score,
                        evidence_text=match_result.evidence_text,
                        evidence_location=match_result.evidence_location,
                        match_method=match_result.match_method,
                        needs_review=match_result.needs_review,
                        engine_versions=json.dumps(
                            {"evaluator": self.engine.ENGINE_VERSION}
                        ),
                    )
                    results.append(match_id)

        self._update_stage_status(project_id, "compliance_status", "completed")
        return results

    def get_matrix(self, project_id: str) -> ComplianceMatrixResponse:
        """获取符合性矩阵"""
        requirements = self.repo.list_by_project(project_id)
        matches = self.compliance_repo.list_by_project(project_id)

        supplier_names = self._get_supplier_names(project_id)

        rows: list[ComplianceMatrixRow] = []
        for req in requirements:
            req_matches = [
                m for m in matches if m["requirement_item_id"] == req["id"]
            ]
            suppliers: dict[str, ComplianceMatrixCell] = {}
            for m in req_matches:
                suppliers[m["supplier_file_id"]] = ComplianceMatrixCell(
                    match_id=m["id"],
                    status=m["status"],
                    is_acceptable=bool(m.get("is_acceptable", 0)),
                    needs_review=bool(m.get("needs_review", 1)),
                    evidence_text=m.get("evidence_text"),
                )
            rows.append(
                ComplianceMatrixRow(
                    requirement=self._to_response(req),
                    suppliers=suppliers,
                )
            )

        return ComplianceMatrixResponse(supplier_names=supplier_names, rows=rows)

    def confirm_match(self, match_id: str, status: str) -> dict:
        """人工确认匹配结果"""
        now = datetime.now(UTC).isoformat()
        self.compliance_repo.update_status(match_id, status, confirmed_at=now)

        match_row = self.compliance_repo.get_by_id(match_id)
        req = self.repo.get_by_id(match_row["requirement_item_id"])  # type: ignore[index]
        self._propagate_comparison_dirty(req["project_id"])  # type: ignore[index]
        return match_row  # type: ignore[return-value]

    def accept_match(self, match_id: str, is_acceptable: bool) -> dict:
        """标记部分符合为可接受"""
        self.compliance_repo.update_acceptable(match_id, is_acceptable)

        match_row = self.compliance_repo.get_by_id(match_id)
        req = self.repo.get_by_id(match_row["requirement_item_id"])  # type: ignore[index]
        self._propagate_comparison_dirty(req["project_id"])  # type: ignore[index]
        return match_row  # type: ignore[return-value]

    # [C3-fix] 供 Task 4.3 API 层调用
    def get_match(self, match_id: str) -> dict | None:
        """获取单条匹配结果"""
        return self.compliance_repo.get_by_id(match_id)

    # ---- 供资格判定 ----

    def get_eligible_supplier_ids(self, group_id: str) -> list[str]:
        return self.compliance_repo.get_eligible_supplier_ids(group_id)

    # ---- 私有方法 ----

    def _generate_code(self, project_id: str) -> str:
        count = self.repo.count_by_project(project_id)
        return f"REQ-{count + 1:03d}"

    def _activate_compliance_stage(self, project_id: str) -> None:
        """首次新增需求项时激活符合性阶段"""
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE projects SET compliance_status = 'pending', updated_at = ?
                   WHERE id = ? AND compliance_status = 'skipped'""",
                (now, project_id),
            )

    def _deactivate_compliance_stage(self, project_id: str) -> None:
        """删除所有需求项后恢复 skipped"""
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET compliance_status = 'skipped', updated_at = ? WHERE id = ?",
                (now, project_id),
            )

    def _propagate_dirty(self, project_id: str) -> None:
        """需求变更 → compliance dirty → comparison dirty"""
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

    def _to_response(self, row: dict) -> RequirementResponse:
        return RequirementResponse(
            id=row["id"],
            project_id=row["project_id"],
            code=row.get("code"),
            category=row["category"],
            title=row["title"],
            description=row.get("description"),
            is_mandatory=bool(row.get("is_mandatory", 1)),
            match_type=row["match_type"],
            expected_value=row.get("expected_value"),
            operator=row.get("operator"),
            sort_order=row.get("sort_order", 0),
            created_at=row["created_at"],
        )

    # [M4] 仅对 confirmed 状态的归组执行匹配
    def _get_confirmed_groups(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM commodity_groups WHERE project_id = ? AND status = 'confirmed'",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_supplier_rows_for_group(self, group_id: str) -> dict[str, list[dict]]:
        """返回 {supplier_file_id: [standardized_row, ...]}"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sr.supplier_file_id as sfid
                   FROM group_members gm
                   JOIN standardized_rows sr ON sr.id = gm.standardized_row_id
                   WHERE gm.group_id = ?""",
                (group_id,),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        result: dict[str, list[dict]] = {}
        for row in rows:
            sid = row["supplier_file_id"]
            result.setdefault(sid, []).append(row)
        return result

    def _get_supplier_names(self, project_id: str) -> dict[str, str]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT id, supplier_name FROM supplier_files WHERE project_id = ?",
                (project_id,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def _propagate_comparison_dirty(self, project_id: str) -> None:
        """符合性结果变更 → comparison dirty"""
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET comparison_status = 'dirty', updated_at = ? WHERE id = ?",
                (now, project_id),
            )

    def _update_stage_status(
        self, project_id: str, stage: str, status: str
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {stage} = ?, updated_at = ? WHERE id = ?",  # noqa: S608
                (status, now, project_id),
            )
