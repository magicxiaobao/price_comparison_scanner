from __future__ import annotations

from db.database import Database


class ComplianceRepo:
    """compliance_matches 表操作 — 纯数据访问层"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        match_id: str,
        requirement_item_id: str,
        commodity_group_id: str,
        supplier_file_id: str,
        status: str,
        is_acceptable: bool,
        match_score: float | None,
        evidence_text: str | None,
        evidence_location: str | None,
        match_method: str | None,
        needs_review: bool,
        engine_versions: str | None,
    ) -> dict:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO compliance_matches
                   (id, requirement_item_id, commodity_group_id, supplier_file_id,
                    status, is_acceptable, match_score, evidence_text, evidence_location,
                    match_method, needs_review, engine_versions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    match_id, requirement_item_id, commodity_group_id,
                    supplier_file_id, status, 1 if is_acceptable else 0,
                    match_score, evidence_text, evidence_location,
                    match_method, 1 if needs_review else 0, engine_versions,
                ),
            )
        return self.get_by_id(match_id)  # type: ignore[return-value]

    def get_by_id(self, match_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM compliance_matches WHERE id = ?", (match_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        """通过 requirement_items JOIN 获取项目所有匹配结果"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.*, ri.project_id
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   WHERE ri.project_id = ?""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_by_requirement(self, requirement_item_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM compliance_matches WHERE requirement_item_id = ?",
                (requirement_item_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_by_group_and_supplier(
        self, group_id: str, supplier_file_id: str
    ) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM compliance_matches
                   WHERE commodity_group_id = ? AND supplier_file_id = ?""",
                (group_id, supplier_file_id),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_status(
        self, match_id: str, status: str, confirmed_at: str | None = None
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE compliance_matches
                   SET status = ?, needs_review = 0, confirmed_at = ?
                   WHERE id = ?""",
                (status, confirmed_at, match_id),
            )

    def update_acceptable(self, match_id: str, is_acceptable: bool) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE compliance_matches SET is_acceptable = ? WHERE id = ?",
                (1 if is_acceptable else 0, match_id),
            )

    def delete_by_project(self, project_id: str) -> int:
        """删除项目所有匹配结果（重新评估前调用）"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """DELETE FROM compliance_matches
                   WHERE requirement_item_id IN
                     (SELECT id FROM requirement_items WHERE project_id = ?)""",
                (project_id,),
            )
            return cursor.rowcount

    def get_eligible_supplier_ids(self, group_id: str) -> list[str]:
        """返回该商品组中有资格参与有效最低价的供应商 ID 列表"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT DISTINCT cm.supplier_file_id
                   FROM compliance_matches cm
                   WHERE cm.commodity_group_id = ?""",
                (group_id,),
            )
            all_suppliers = [row[0] for row in cursor.fetchall()]
            if not all_suppliers:
                return []  # 无需求标准，由调用方处理

            eligible: list[str] = []
            for sid in all_suppliers:
                cursor = conn.execute(
                    """SELECT cm.status, cm.is_acceptable, ri.is_mandatory
                       FROM compliance_matches cm
                       JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                       WHERE cm.commodity_group_id = ? AND cm.supplier_file_id = ?""",
                    (group_id, sid),
                )
                rows = cursor.fetchall()
                is_eligible = True
                for row in rows:
                    status, is_acceptable, is_mandatory = row[0], row[1], row[2]
                    if is_mandatory:
                        if status == "no_match":
                            is_eligible = False
                            break
                        if status == "unclear" and not is_acceptable:
                            is_eligible = False
                            break
                        if status == "partial" and not is_acceptable:
                            is_eligible = False
                            break
                if is_eligible:
                    eligible.append(sid)

            return eligible
