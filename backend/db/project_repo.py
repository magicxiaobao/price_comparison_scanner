from db.database import Database


class ProjectRepo:
    """项目表 CRUD 操作 — Task 0.4 填充实现"""

    def __init__(self, db: Database) -> None:
        self.db = db
