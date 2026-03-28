from __future__ import annotations

from datetime import UTC, datetime

from db.database import Database


class RequirementRepo:
    """requirement_items 表操作 — 纯数据访问层"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        req_id: str,
        project_id: str,
        code: str | None,
        category: str,
        title: str,
        description: str | None,
        is_mandatory: bool,
        match_type: str,
        expected_value: str | None,
        operator: str | None,
        sort_order: int,
    ) -> dict:
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO requirement_items
                   (id, project_id, code, category, title, description,
                    is_mandatory, match_type, expected_value, operator, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req_id, project_id, code, category, title, description,
                    1 if is_mandatory else 0, match_type, expected_value, operator,
                    sort_order, now,
                ),
            )
        return self.get_by_id(req_id)  # type: ignore[return-value]

    def get_by_id(self, req_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM requirement_items WHERE id = ?", (req_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM requirement_items WHERE project_id = ? ORDER BY sort_order, created_at",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update(self, req_id: str, updates: dict) -> dict | None:
        """部分更新需求项，updates 为字段名→值的 dict"""
        if not updates:
            return self.get_by_id(req_id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [req_id]
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE requirement_items SET {set_clause} WHERE id = ?",  # noqa: S608
                values,
            )
        return self.get_by_id(req_id)

    def delete(self, req_id: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM requirement_items WHERE id = ?", (req_id,)
            )
            return cursor.rowcount > 0

    def count_by_project(self, project_id: str) -> int:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return int(cursor.fetchone()[0])

    def get_max_sort_order(self, project_id: str) -> int:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return int(cursor.fetchone()[0])

    def delete_all_by_project(self, project_id: str) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount
