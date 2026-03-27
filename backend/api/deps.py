from pathlib import Path

import config
from db.database import Database


def get_app_data_dir() -> Path:
    """获取应用数据目录，不存在则创建"""
    path = Path(config.settings.APP_DATA_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_global_config_path() -> Path:
    return get_app_data_dir() / "config.json"


def get_project_db(project_id: str) -> Database:
    """获取项目数据库实例"""
    project_dir = get_app_data_dir() / "projects" / project_id
    return Database(project_dir / "project.db")
