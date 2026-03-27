import json
import os
import shutil
import uuid
from pathlib import Path

from config import get_app_data_dir
from db.database import Database
from db.project_repo import ProjectRepo
from models.project import ProjectCreate, ProjectDetail, ProjectSummary, StageStatuses


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
