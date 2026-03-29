import re
import uuid
from pathlib import Path

from config import get_app_data_dir
from db.database import Database
from db.file_repo import FileRepo
from db.table_repo import TableRepo
from engines.document_parser import DocumentParser
from engines.task_manager import get_task_manager


class FileService:
    """文件导入业务编排"""

    def __init__(self) -> None:
        self._parser = DocumentParser()

    def import_file(self, project_id: str, original_filename: str,
                    file_content: bytes) -> dict:
        """
        导入文件：
        1. 复制到 source_files/ 目录
        2. 猜测供应商名称
        3. 在数据库中创建 supplier_file 记录
        4. 通过 TaskManager 提交异步解析任务
        5. 返回 {file_id, task_id, supplier_name_guess}
        """
        file_id = str(uuid.uuid4())
        suffix = Path(original_filename).suffix.lower().lstrip(".")

        if suffix not in DocumentParser.SUPPORTED_TYPES:
            raise ValueError(f"不支持的文件类型: {suffix}")

        project_dir = get_app_data_dir() / "projects" / project_id
        source_dir = project_dir / "source_files"
        source_dir.mkdir(parents=True, exist_ok=True)
        dest_path = source_dir / f"{file_id}.{suffix}"
        dest_path.write_bytes(file_content)

        supplier_guess = self._guess_supplier_name(original_filename)

        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        file_repo.insert(
            file_id=file_id,
            project_id=project_id,
            supplier_name=supplier_guess,
            original_filename=original_filename,
            file_path=f"source_files/{file_id}.{suffix}",
            file_type=suffix,
            recognition_mode="structure",
        )

        tm = get_task_manager()
        task_id = tm.submit(
            "file_parse",
            self._parse_task,
            project_id, file_id, str(dest_path),
        )

        return {
            "file_id": file_id,
            "task_id": task_id,
            "supplier_name_guess": supplier_guess,
        }

    def _parse_task(self, progress_callback: object, project_id: str,
                    file_id: str, file_path: str) -> dict:
        """
        异步解析任务的执行体。
        解析文件 -> 将 RawTableData 写入 raw_tables 表。
        PDF L1 未识别到表格时，标记 recognition_mode = "manual"。
        """
        tables = self._parser.parse(file_path, progress_callback)  # type: ignore[arg-type]

        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        table_repo = TableRepo(db)

        if not tables and file_path.lower().endswith(".pdf"):
            file_repo.update_recognition_mode(file_id, "manual")
            return {"file_id": file_id, "table_count": 0, "table_ids": []}

        table_ids: list[str] = []
        for t in tables:
            table_id = str(uuid.uuid4())
            raw_data = {"headers": t.headers, "rows": t.rows}
            table_repo.insert(
                table_id=table_id,
                supplier_file_id=file_id,
                table_index=t.table_index,
                sheet_name=t.sheet_name,
                page_number=t.page_number,
                row_count=t.row_count,
                column_count=t.column_count,
                raw_data=raw_data,
            )
            table_ids.append(table_id)

        return {"file_id": file_id, "table_count": len(table_ids), "table_ids": table_ids}

    def confirm_supplier(self, file_id: str, supplier_name: str,
                         project_id: str) -> dict | None:
        """确认供应商名称"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        return file_repo.confirm_supplier(file_id, supplier_name)

    def get_tables(self, project_id: str) -> list[dict]:
        """获取项目的所有解析表格"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        table_repo = TableRepo(db)
        return table_repo.list_by_project(project_id)

    def toggle_table_selection(self, table_id: str, project_id: str) -> dict | None:
        """切换表格参与比价状态"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        table_repo = TableRepo(db)
        return table_repo.toggle_selection(table_id)

    def find_file(self, file_id: str) -> tuple[dict | None, str | None]:
        """跨项目查找文件记录，返回 (file_record, project_id)"""
        import json
        config_path = get_app_data_dir() / "config.json"
        if not config_path.exists():
            return None, None
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for p in config.get("recent_projects", []):
            project_dir = Path(p["path"])
            db_path = project_dir / "project.db"
            if not db_path.exists():
                continue
            db = Database(db_path)
            file_repo = FileRepo(db)
            record = file_repo.get_by_id(file_id)
            if record:
                return record, p["id"]
        return None, None

    def delete_file(self, file_id: str, project_id: str) -> bool:
        """删除文件：删除磁盘文件 + 数据库记录（CASCADE 自动清理关联表）"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)

        record = file_repo.get_by_id(file_id)
        if not record:
            return False

        # 删除磁盘上的源文件
        source_file = project_dir / record["file_path"]
        if source_file.exists():
            source_file.unlink()

        # 删除数据库记录（ON DELETE CASCADE 清理 raw_tables → standardized_rows 等）
        return file_repo.delete(file_id)

    def get_files(self, project_id: str) -> list[dict]:
        """获取项目的所有文件"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        return file_repo.list_by_project(project_id)

    @staticmethod
    def _guess_supplier_name(filename: str) -> str:
        """
        根据文件名猜测供应商名称。
        规则：去掉扩展名、常见后缀、日期模式，返回剩余部分。
        """
        name = Path(filename).stem
        name = re.sub(r"[_\-\s]*(报价单|报价表|报价|价格表|询价回复|回标)", "", name)
        name = re.sub(r"\d{4}[-/]?\d{2}[-/]?\d{2}", "", name)
        name = name.strip(" _-")
        return name if name else "未知供应商"
