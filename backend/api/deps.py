from config import get_app_data_dir, get_global_config_path
from db.database import Database


def get_project_db(project_id: str) -> Database:
    """获取项目数据库实例"""
    project_dir = get_app_data_dir() / "projects" / project_id
    return Database(project_dir / "project.db")


__all__ = ["get_app_data_dir", "get_global_config_path", "get_project_db"]
