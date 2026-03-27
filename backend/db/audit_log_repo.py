from __future__ import annotations

from db.database import Database


class AuditLogRepo:
    """审计日志数据访问层 — 纯 SQL 操作"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        log_id: str,
        project_id: str,
        action_type: str,
        action_source: str,
        target_table: str | None,
        target_id: str | None,
        field_name: str | None,
        before_value: str | None,
        after_value: str | None,
        created_at: str,
    ) -> dict:
        """插入一条审计日志"""
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO audit_logs
                   (id, project_id, action_type, action_source,
                    target_table, target_id, field_name,
                    before_value, after_value, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id, project_id, action_type, action_source,
                    target_table, target_id, field_name,
                    before_value, after_value, created_at,
                ),
            )
        return self._get_by_id(log_id)

    def list_by_project(self, project_id: str, limit: int = 100) -> list[dict]:
        """按项目 ID 查询审计日志，按时间降序"""
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM audit_logs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_by_target(self, target_id: str) -> list[dict]:
        """按目标记录 ID 查询审计日志"""
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM audit_logs WHERE target_id = ? ORDER BY created_at DESC",
                (target_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_by_id(self, log_id: str) -> dict:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
