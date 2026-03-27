from __future__ import annotations

import uuid
from datetime import UTC, datetime

from db.audit_log_repo import AuditLogRepo
from db.database import Database


class AuditLogService:
    """操作留痕服务 — 记录所有修改操作到 audit_logs 表"""

    def __init__(self, db: Database) -> None:
        self.repo = AuditLogRepo(db)

    def log(
        self,
        project_id: str,
        action_type: str,
        action_source: str = "user",
        target_table: str | None = None,
        target_id: str | None = None,
        field_name: str | None = None,
        before_value: str | None = None,
        after_value: str | None = None,
    ) -> str:
        """记录一条操作日志，返回 log_id"""
        log_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        # 数值型统一转字符串
        if before_value is not None and not isinstance(before_value, str):
            before_value = str(before_value)
        if after_value is not None and not isinstance(after_value, str):
            after_value = str(after_value)
        self.repo.insert(
            log_id=log_id,
            project_id=project_id,
            action_type=action_type,
            action_source=action_source,
            target_table=target_table,
            target_id=target_id,
            field_name=field_name,
            before_value=before_value,
            after_value=after_value,
            created_at=now,
        )
        return log_id

    def get_project_logs(self, project_id: str, limit: int = 100) -> list[dict]:
        """获取项目的操作日志"""
        return self.repo.list_by_project(project_id, limit)

    def get_target_logs(self, target_id: str) -> list[dict]:
        """获取某个目标记录的操作日志"""
        return self.repo.list_by_target(target_id)
