from datetime import UTC, datetime

from db.database import Database


class ProjectRepo:
    """项目表 CRUD — 纯数据访问层，不负责生成 ID 或管理目录"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, project_id: str, name: str) -> dict:
        """插入项目记录，返回项目 dict。ID 由调用方（service）提供。"""
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (project_id, name, now, now),
            )
        row = self.get_by_id(project_id)
        assert row is not None
        return row

    def get_by_id(self, project_id: str) -> dict | None:
        """按 ID 查询项目，返回 dict 或 None"""
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_all(self) -> list[dict]:
        """查询所有项目，按更新时间降序"""
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete(self, project_id: str) -> bool:
        """删除项目记录，返回是否有实际删除"""
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0
