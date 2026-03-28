from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from db.database import Database
from db.requirement_repo import RequirementRepo
from engines.compliance_evaluator import ComplianceEvaluator
from models.compliance import (
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
