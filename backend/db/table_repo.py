import json
from typing import Any

from db.database import Database


class TableRepo:
    """raw_tables 表 CRUD"""

    def __init__(self, db: Database):
        self.db = db

    def insert(self, table_id: str, supplier_file_id: str, table_index: int,
               sheet_name: str | None, page_number: int | None,
               row_count: int, column_count: int, raw_data: dict) -> dict:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO raw_tables
                   (id, supplier_file_id, table_index, sheet_name, page_number,
                    row_count, column_count, raw_data, selected)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (table_id, supplier_file_id, table_index, sheet_name,
                 page_number, row_count, column_count, json.dumps(raw_data, ensure_ascii=False)),
            )
        return self.get_by_id(table_id)  # type: ignore[return-value]

    def get_by_id(self, table_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM raw_tables WHERE id = ?", (table_id,))
            row = cursor.fetchone()
            return self._deserialize_row(row) if row else None

    @staticmethod
    def _deserialize_row(row: Any) -> dict:
        d = dict(row)
        if isinstance(d.get("raw_data"), str):
            d["raw_data"] = json.loads(d["raw_data"])
        return d

    def list_by_project(self, project_id: str) -> list[dict]:
        """通过 supplier_files 关联查询项目的所有表格"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT rt.*, sf.supplier_name, sf.original_filename, sf.supplier_confirmed
                   FROM raw_tables rt
                   JOIN supplier_files sf ON rt.supplier_file_id = sf.id
                   WHERE sf.project_id = ?
                   ORDER BY sf.imported_at, rt.table_index""",
                (project_id,),
            )
            return [self._deserialize_row(row) for row in cursor.fetchall()]

    def list_by_file(self, supplier_file_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM raw_tables WHERE supplier_file_id = ? ORDER BY table_index",
                (supplier_file_id,),
            )
            return [self._deserialize_row(row) for row in cursor.fetchall()]

    def toggle_selection(self, table_id: str) -> dict | None:
        """切换 selected 状态（0 <-> 1）"""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE raw_tables SET selected = CASE WHEN selected = 1 THEN 0 ELSE 1 END WHERE id = ?",
                (table_id,),
            )
        return self.get_by_id(table_id)
