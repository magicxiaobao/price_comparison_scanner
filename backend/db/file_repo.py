from datetime import UTC, datetime

from db.database import Database


class FileRepo:
    """supplier_files 表 CRUD"""

    def __init__(self, db: Database):
        self.db = db

    def insert(self, file_id: str, project_id: str, supplier_name: str,
               original_filename: str, file_path: str, file_type: str,
               recognition_mode: str) -> dict:
        now = datetime.now(UTC).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO supplier_files
                   (id, project_id, supplier_name, supplier_confirmed,
                    original_filename, file_path, file_type, recognition_mode, imported_at)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (file_id, project_id, supplier_name, original_filename,
                 file_path, file_type, recognition_mode, now),
            )
        return self.get_by_id(file_id)  # type: ignore[return-value]

    def get_by_id(self, file_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM supplier_files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM supplier_files WHERE project_id = ? ORDER BY imported_at",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def confirm_supplier(self, file_id: str, supplier_name: str) -> dict | None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE supplier_files SET supplier_name = ?, supplier_confirmed = 1 WHERE id = ?",
                (supplier_name, file_id),
            )
        return self.get_by_id(file_id)

    def update_recognition_mode(self, file_id: str, mode: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE supplier_files SET recognition_mode = ? WHERE id = ?",
                (mode, file_id),
            )

    def delete(self, file_id: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM supplier_files WHERE id = ?", (file_id,))
            return cursor.rowcount > 0
