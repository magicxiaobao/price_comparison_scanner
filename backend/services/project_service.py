from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from config import get_app_data_dir
from db.database import Database
from db.file_repo import FileRepo
from db.project_repo import ProjectRepo
from db.standardized_row_repo import StandardizedRowRepo
from db.table_repo import TableRepo
from engines.rule_engine import RuleEngine
from engines.table_standardizer import STANDARD_FIELDS, TableStandardizer
from engines.task_manager import get_task_manager
from models.project import ProjectCreate, ProjectDetail, ProjectSummary, StageStatuses
from services.audit_log_service import AuditLogService


class ProjectService:
    """
    项目业务服务 — 协调目录管理、数据库操作、全局配置。
    职责边界：service 负责 ID 生成、目录创建、全局配置更新；repo 负责纯 SQL 操作。
    """

    def create_project(self, req: ProjectCreate) -> ProjectDetail:
        """新建项目：生成 ID -> 创建目录 -> 初始化数据库 -> 通过 repo 写入记录 -> 更新全局配置"""
        app_data = get_app_data_dir()
        project_id = str(uuid.uuid4())
        project_dir = app_data / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "source_files").mkdir(exist_ok=True)
        (project_dir / "exports").mkdir(exist_ok=True)

        db = Database(project_dir / "project.db")
        repo = ProjectRepo(db)
        repo.insert(project_id, req.name)

        self._update_recent_projects(project_id, req.name, project_dir)

        row = repo.get_by_id(project_id)
        assert row is not None
        return self._to_detail(row)

    def list_projects(self) -> list[ProjectSummary]:
        """从全局配置读取最近项目列表"""
        config = self._read_global_config()
        result: list[ProjectSummary] = []
        for p in config.get("recent_projects", []):
            project_dir = Path(p["path"])
            if not (project_dir / "project.db").exists():
                continue
            db = Database(project_dir / "project.db")
            repo = ProjectRepo(db)
            row = repo.get_by_id(p["id"])
            if row:
                result.append(self._to_summary(row))
        return result

    def get_project(self, project_id: str) -> ProjectDetail | None:
        """获取项目详情"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            return None
        db = Database(project_dir / "project.db")
        repo = ProjectRepo(db)
        row = repo.get_by_id(project_id)
        return self._to_detail(row) if row else None

    def delete_project(self, project_id: str) -> bool:
        """删除项目：删除目录 + 从全局配置移除"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            return False
        if project_dir.exists():
            shutil.rmtree(project_dir)
        self._remove_from_recent(project_id)
        return True

    # ---- 标准化相关 ----

    def run_standardization(self, project_id: str, force: bool = False) -> str:
        """执行标准化（异步任务），返回 task_id"""
        tm = get_task_manager()
        task_id = tm.submit(
            "standardize",
            self._standardize_task,
            project_id,
            force,
        )
        return task_id

    def _standardize_task(
        self, progress_callback: object, project_id: str, force: bool
    ) -> dict:
        """标准化异步执行体"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            raise ValueError(f"项目不存在: {project_id}")

        db = Database(project_dir / "project.db")
        table_repo = TableRepo(db)
        std_repo = StandardizedRowRepo(db)
        audit_svc = AuditLogService(db)

        rules_dir = get_app_data_dir() / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_engine = RuleEngine(rules_dir)
        # 确保默认规则存在
        if not (rules_dir / "user-rules.json").exists():
            rule_engine.reset_default()
        standardizer = TableStandardizer(rule_engine)
        rules = rule_engine.load_global_rules()

        file_repo = FileRepo(db)
        files = file_repo.list_by_project(project_id)
        file_type_map = {f["id"]: f["file_type"] for f in files}

        raw_tables = table_repo.list_by_project(project_id)
        selected_tables = [t for t in raw_tables if t.get("selected", 1)]

        if not selected_tables:
            return {"project_id": project_id, "row_count": 0}

        if force:
            std_repo.delete_by_project(project_id)

        total = len(selected_tables)
        all_rows: list[dict] = []

        for idx, rt in enumerate(selected_tables):
            if force:
                std_repo.delete_by_raw_table(rt["id"])

            raw_data = rt.get("raw_data", {})
            headers = raw_data.get("headers", [])
            rows = raw_data.get("rows", [])

            result = standardizer.standardize(
                raw_table_id=rt["id"],
                supplier_file_id=rt["supplier_file_id"],
                headers=headers,
                rows=rows,
                file_type=file_type_map.get(rt["supplier_file_id"], "xlsx"),
                sheet_name=rt.get("sheet_name"),
                page_number=rt.get("page_number"),
                table_index=rt.get("table_index", 0),
                rules=rules,
            )

            row_dicts = [r.model_dump() for r in result.rows]
            # Serialize nested Pydantic models in source_location
            for rd in row_dicts:
                if rd.get("source_location"):
                    rd["source_location"] = {
                        k: v.model_dump() if hasattr(v, "model_dump") else v
                        for k, v in rd["source_location"].items()
                    }
                if rd.get("hit_rule_snapshots"):
                    rd["hit_rule_snapshots"] = [
                        s.model_dump() if hasattr(s, "model_dump") else s
                        for s in rd["hit_rule_snapshots"]
                    ]
            all_rows.extend(row_dicts)

            if callable(progress_callback):
                progress_callback((idx + 1) / total)  # type: ignore[operator]

        if all_rows:
            std_repo.insert_batch(all_rows)

        # 记录审计日志
        audit_svc.log(
            project_id=project_id,
            action_type="standardize",
            action_source="system",
            target_table="standardized_rows",
        )

        # 更新项目标准化状态
        now = datetime.now(UTC).isoformat()
        with db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET normalize_status = 'completed', normalize_completed_at = ?, updated_at = ? WHERE id = ?",
                (now, now, project_id),
            )

        return {"project_id": project_id, "row_count": len(all_rows)}

    def get_standardized_rows(self, project_id: str) -> list[dict]:
        """获取项目所有标准化行"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            return []
        db = Database(project_dir / "project.db")
        std_repo = StandardizedRowRepo(db)
        return std_repo.get_by_project(project_id)

    def modify_standardized_row(
        self, row_id: str, field: str, new_value: str | float | None
    ) -> dict:
        """手工修正标准化行字段"""
        if field not in STANDARD_FIELDS:
            raise ValueError(f"无效字段: {field}")

        # 需要找到 row 所属的项目
        project_id, project_dir = self._find_project_for_row(row_id)
        if not project_dir:
            raise ValueError(f"标准化行不存在: {row_id}")

        db = Database(project_dir / "project.db")
        std_repo = StandardizedRowRepo(db)
        audit_svc = AuditLogService(db)

        old_row = std_repo.get_by_id(row_id)
        if not old_row:
            raise ValueError(f"标准化行不存在: {row_id}")

        old_value = old_row.get(field)

        updated_row = std_repo.update_field(row_id, field, new_value)
        if not updated_row:
            raise ValueError(f"更新失败: {row_id}")

        # 审计日志
        log_id = audit_svc.log(
            project_id=project_id,
            action_type="modify_field",
            action_source="user",
            target_table="standardized_rows",
            target_id=row_id,
            field_name=field,
            before_value=old_value,
            after_value=new_value,
        )

        # 失效传播
        dirty_stages = self._propagate_dirty(project_id, db, "normalize")

        return {
            "success": True,
            "audit_log": {
                "id": log_id,
                "action_type": "modify_field",
                "field_name": field,
                "before_value": str(old_value) if old_value is not None else None,
                "after_value": str(new_value) if new_value is not None else None,
            },
            "dirty_stages": dirty_stages,
        }

    def get_column_mapping_info(self, project_id: str) -> list[dict]:
        """获取项目的列名映射信息"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            return []
        db = Database(project_dir / "project.db")
        std_repo = StandardizedRowRepo(db)
        rows = std_repo.get_by_project(project_id)
        if not rows:
            return []
        # Use column_mapping from first row as representative
        first = rows[0]
        mapping = first.get("column_mapping") or {}
        return [
            {
                "originalColumn": col,
                "targetField": mapping.get(col),
                "status": "confirmed" if col in mapping else "unmapped",
            }
            for col in mapping
        ]

    def _propagate_dirty(
        self, project_id: str, db: Database, from_stage: str
    ) -> list[str]:
        """失效传播：从指定阶段开始，将下游阶段标记为 dirty"""
        stage_order = ["normalize", "grouping", "compliance", "comparison"]
        if from_stage not in stage_order:
            return []

        start_idx = stage_order.index(from_stage) + 1
        dirty_stages: list[str] = []

        # 读取当前状态
        with db.read() as conn:
            cursor = conn.execute(
                "SELECT compliance_status FROM projects WHERE id = ?", (project_id,)
            )
            row = cursor.fetchone()
            current_compliance = dict(row).get("compliance_status") if row else None

        now = datetime.now(UTC).isoformat()
        with db.transaction() as conn:
            for stage in stage_order[start_idx:]:
                status_field = f"{stage}_status"
                # compliance=skipped 时不改为 dirty
                if stage == "compliance" and current_compliance == "skipped":
                    continue
                conn.execute(
                    f"UPDATE projects SET {status_field} = 'dirty', updated_at = ? WHERE id = ?",  # noqa: S608
                    (now, project_id),
                )
                dirty_stages.append(stage)

        return dirty_stages

    def _find_project_for_row(self, row_id: str) -> tuple[str, Path | None]:
        """通过 row_id 找到所属项目 ID 和目录"""
        config = self._read_global_config()
        for p in config.get("recent_projects", []):
            project_dir = Path(p["path"])
            db_path = project_dir / "project.db"
            if not db_path.exists():
                continue
            db = Database(db_path)
            std_repo = StandardizedRowRepo(db)
            row = std_repo.get_by_id(row_id)
            if row:
                return p["id"], project_dir
        return "", None

    # ---- 私有方法 ----

    def _find_project_dir(self, project_id: str) -> Path | None:
        config = self._read_global_config()
        for p in config.get("recent_projects", []):
            if p["id"] == project_id:
                return Path(p["path"])
        return None

    def _read_global_config(self) -> dict:
        config_path = get_app_data_dir() / "config.json"
        if not config_path.exists():
            return {"recent_projects": []}
        return json.loads(config_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    def _write_global_config(self, config: dict) -> None:
        """原子写入：临时文件 -> fsync -> rename"""
        config_path = get_app_data_dir() / "config.json"
        tmp_path = config_path.with_suffix(".tmp")
        data = json.dumps(config, ensure_ascii=False, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(config_path)

    def _update_recent_projects(self, project_id: str, name: str, project_dir: Path) -> None:
        config = self._read_global_config()
        recent: list[dict] = config.get("recent_projects", [])
        recent = [p for p in recent if p["id"] != project_id]
        recent.insert(0, {"id": project_id, "name": name, "path": str(project_dir)})
        config["recent_projects"] = recent
        self._write_global_config(config)

    def _remove_from_recent(self, project_id: str) -> None:
        config = self._read_global_config()
        config["recent_projects"] = [
            p for p in config.get("recent_projects", []) if p["id"] != project_id
        ]
        self._write_global_config(config)

    def _to_summary(self, row: dict) -> ProjectSummary:
        return ProjectSummary(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _to_detail(self, row: dict) -> ProjectDetail:
        return ProjectDetail(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            stage_statuses=StageStatuses(
                import_status=row.get("import_status", "pending"),
                normalize_status=row.get("normalize_status", "pending"),
                grouping_status=row.get("grouping_status", "pending"),
                compliance_status=row.get("compliance_status", "skipped"),
                comparison_status=row.get("comparison_status", "pending"),
            ),
        )
