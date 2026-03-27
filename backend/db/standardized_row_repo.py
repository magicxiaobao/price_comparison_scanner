from __future__ import annotations

import json

from db.database import Database


class StandardizedRowRepo:
    """标准化行数据访问层"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert_batch(self, rows: list[dict]) -> int:
        """批量插入标准化行，返回插入行数"""
        if not rows:
            return 0
        with self.db.transaction() as conn:
            for row in rows:
                conn.execute(
                    """INSERT INTO standardized_rows
                       (id, raw_table_id, supplier_file_id, row_index,
                        product_name, spec_model, unit, quantity, unit_price,
                        total_price, tax_rate, delivery_period, remark,
                        source_location, column_mapping, hit_rule_snapshots,
                        confidence, is_manually_modified, needs_review, tax_basis)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["id"],
                        row["raw_table_id"],
                        row["supplier_file_id"],
                        row["row_index"],
                        row.get("product_name"),
                        row.get("spec_model"),
                        row.get("unit"),
                        row.get("quantity"),
                        row.get("unit_price"),
                        row.get("total_price"),
                        row.get("tax_rate"),
                        row.get("delivery_period"),
                        row.get("remark"),
                        json.dumps(row["source_location"], ensure_ascii=False),
                        json.dumps(row.get("column_mapping"), ensure_ascii=False)
                        if row.get("column_mapping") is not None
                        else None,
                        json.dumps(row.get("hit_rule_snapshots"), ensure_ascii=False)
                        if row.get("hit_rule_snapshots") is not None
                        else None,
                        row.get("confidence", 1.0),
                        1 if row.get("is_manually_modified") else 0,
                        1 if row.get("needs_review") else 0,
                        row.get("tax_basis"),
                    ),
                )
        return len(rows)

    def get_by_project(self, project_id: str) -> list[dict]:
        """按项目 ID 查询所有标准化行（通过 supplier_file_id JOIN）"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*
                   FROM standardized_rows sr
                   JOIN supplier_files sf ON sr.supplier_file_id = sf.id
                   WHERE sf.project_id = ?
                   ORDER BY sr.supplier_file_id, sr.row_index""",
                (project_id,),
            )
            return [self._deserialize_row(row) for row in cursor.fetchall()]

    def get_by_id(self, row_id: str) -> dict | None:
        """按 ID 查询单行"""
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM standardized_rows WHERE id = ?", (row_id,)
            )
            row = cursor.fetchone()
            return self._deserialize_row(row) if row else None

    def update_field(
        self, row_id: str, field_name: str, new_value: str | float | None
    ) -> dict | None:
        """更新单个字段值，同时设置 is_manually_modified=1，返回更新后的行"""
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE standardized_rows SET {field_name} = ?, is_manually_modified = 1 WHERE id = ?",  # noqa: S608
                (new_value, row_id),
            )
        return self.get_by_id(row_id)

    def delete_by_raw_table(self, raw_table_id: str) -> int:
        """按 raw_table_id 删除标准化行（重新标准化前清理）"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM standardized_rows WHERE raw_table_id = ?",
                (raw_table_id,),
            )
            return cursor.rowcount

    def delete_by_project(self, project_id: str) -> int:
        """按项目删除所有标准化行"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """DELETE FROM standardized_rows
                   WHERE supplier_file_id IN (
                       SELECT id FROM supplier_files WHERE project_id = ?
                   )""",
                (project_id,),
            )
            return cursor.rowcount

    @staticmethod
    def _deserialize_row(row: object) -> dict:
        d = dict(row)  # type: ignore[call-overload]
        for json_field in ("source_location", "column_mapping", "hit_rule_snapshots"):
            if isinstance(d.get(json_field), str):
                d[json_field] = json.loads(d[json_field])
        d["is_manually_modified"] = bool(d.get("is_manually_modified"))
        d["needs_review"] = bool(d.get("needs_review"))
        return dict(d)
