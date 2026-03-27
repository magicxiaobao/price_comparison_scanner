
from db.database import Database


class GroupRepo:
    """commodity_groups + group_members 表操作 — 纯数据访问层"""

    def __init__(self, db: Database):
        self.db = db

    def insert_group(
        self,
        group_id: str,
        project_id: str,
        group_name: str,
        normalized_key: str,
        confidence_level: str,
        engine_versions: str,
        match_score: float,
        match_reason: str,
        status: str = "candidate",
    ) -> dict:
        """插入一条归组记录"""
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO commodity_groups
                   (id, project_id, group_name, normalized_key, confidence_level,
                    engine_versions, match_score, match_reason, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (group_id, project_id, group_name, normalized_key,
                 confidence_level, engine_versions, match_score, match_reason, status),
            )
        result = self.get_group_by_id(group_id)
        assert result is not None
        return result

    def add_member(self, group_id: str, standardized_row_id: str) -> None:
        """添加归组成员"""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id, standardized_row_id) VALUES (?, ?)",
                (group_id, standardized_row_id),
            )

    def add_members(self, group_id: str, row_ids: list[str]) -> None:
        """批量添加归组成员"""
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO group_members (group_id, standardized_row_id) VALUES (?, ?)",
                [(group_id, rid) for rid in row_ids],
            )

    def get_group_by_id(self, group_id: str) -> dict | None:
        """查询单个归组（不含成员）"""
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM commodity_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_group_members(self, group_id: str) -> list[dict]:
        """查询归组成员（JOIN standardized_rows + supplier_files 获取摘要信息）"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT gm.standardized_row_id,
                          sr.product_name, sr.spec_model, sr.unit,
                          sr.unit_price, sr.quantity, sr.confidence,
                          sf.supplier_name
                   FROM group_members gm
                   JOIN standardized_rows sr ON sr.id = gm.standardized_row_id
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE gm.group_id = ?""",
                (group_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_groups_by_project(self, project_id: str) -> list[dict]:
        """查询项目所有归组，按置信度排序（high > medium > low）"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM commodity_groups
                   WHERE project_id = ?
                   ORDER BY
                     CASE confidence_level
                       WHEN 'high' THEN 1
                       WHEN 'medium' THEN 2
                       WHEN 'low' THEN 3
                     END,
                     match_score DESC""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_status(self, group_id: str, status: str, confirmed_at: str | None = None) -> None:
        """更新归组状态"""
        with self.db.transaction() as conn:
            if confirmed_at:
                conn.execute(
                    "UPDATE commodity_groups SET status = ?, confirmed_at = ? WHERE id = ?",
                    (status, confirmed_at, group_id),
                )
            else:
                conn.execute(
                    "UPDATE commodity_groups SET status = ? WHERE id = ?",
                    (status, group_id),
                )

    def delete_group(self, group_id: str) -> None:
        """删除归组（CASCADE 会自动删除 group_members）"""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM commodity_groups WHERE id = ?", (group_id,))

    def delete_groups_by_project(self, project_id: str) -> int:
        """删除项目所有归组（重新生成前调用），返回删除数量"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM commodity_groups WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount

    def remove_member(self, group_id: str, standardized_row_id: str) -> None:
        """移除归组成员"""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM group_members WHERE group_id = ? AND standardized_row_id = ?",
                (group_id, standardized_row_id),
            )
