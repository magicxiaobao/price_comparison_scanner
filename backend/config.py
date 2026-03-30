import logging
import os
import shutil
import sys
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.HOST: str = "127.0.0.1"  # 固定绑定本地，禁止 0.0.0.0
        self.PORT: int = int(os.getenv("PORT", "17396"))
        self.SESSION_TOKEN: str = os.getenv("SESSION_TOKEN", "")
        self.DEV_MODE: bool = os.getenv("DEV_MODE", "").lower() in ("1", "true")
        self.APP_DATA_DIR: str = os.getenv("APP_DATA_DIR", os.path.expanduser("~/.price-comparison-scanner"))


settings = Settings()


def get_app_data_dir() -> Path:
    """获取应用数据目录，不存在则创建"""
    path = Path(settings.APP_DATA_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_global_config_path() -> Path:
    """获取全局配置文件路径"""
    return get_app_data_dir() / "config.json"


def setup_error_logger() -> logging.Logger:
    """配置错误日志，写入 {APP_DATA_DIR}/logs/error.log"""
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "error.log"

    logger = logging.getLogger("price-comparison-error")
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
    return logger


error_logger = setup_error_logger()


def init_sample_projects() -> None:
    """首次启动时将内置示例项目拷贝到 app_data/projects/ 并注册到 config.json，仅执行一次"""
    app_data = get_app_data_dir()
    flag = app_data / ".samples_initialized"
    if flag.exists():
        return

    # 定位内置示例数据：PyInstaller 打包后在 _MEIPASS/sample_projects，开发模式在源码目录
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS) / "sample_projects"  # type: ignore[attr-defined]
    else:
        bundle_dir = Path(__file__).parent / "sample_projects"

    if not bundle_dir.exists():
        flag.touch()
        return

    projects_dir = app_data / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    # 读取现有 config.json
    config_path = app_data / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {"recent_projects": []}

    import sqlite3

    copied_any = False
    for src in bundle_dir.iterdir():
        if not src.is_dir():
            continue
        dst = projects_dir / src.name
        if dst.exists():
            continue
        shutil.copytree(src, dst)
        copied_any = True

        # 从 project.db 读取项目名称，注册到 config.json
        db_path = dst / "project.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT id, name FROM projects LIMIT 1").fetchone()
                if row:
                    config["recent_projects"].append({
                        "id": row["id"],
                        "name": row["name"],
                        "path": str(dst),
                    })
                conn.close()
            except Exception:
                pass

    if copied_any:
        tmp_path = config_path.with_suffix(".tmp")
        data = json.dumps(config, ensure_ascii=False, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(config_path)

    flag.touch()
