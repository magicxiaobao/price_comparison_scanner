# Task 0.3: SQLite 数据库层 + Schema 初始化

## 输入条件

- Task 0.1 完成（后端骨架存在）
- 技术架构文档 3.2 节 schema 可参考

## 输出物

- 创建: `backend/db/database.py`
- 创建: `backend/db/schema.sql`
- 创建: `backend/db/project_repo.py`（Phase 0 仅定义骨架，不含 CRUD 实现）
- 创建: `backend/tests/test_database.py`

## 禁止修改

- 不修改 `api/` 下任何文件
- 不修改 `main.py`
- 不修改 `frontend/`

## 实现规格

### db/database.py

```python
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

class Database:
    """SQLite 数据库连接管理器"""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """首次连接时初始化 schema（幂等）"""
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        conn = self._get_connection()
        try:
            # 检查是否已初始化
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            if cursor.fetchone() is None:
                conn.executescript(schema_sql)
                conn.commit()
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """事务上下文管理器：成功 commit，异常 rollback"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Generator[sqlite3.Connection, None, None]:
        """只读连接上下文管理器"""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()
```

**设计要点：**
- 每次 `_get_connection()` 都执行 `PRAGMA foreign_keys = ON`（SQLite 要求每个连接设置）
- `row_factory = sqlite3.Row` 使查询结果可以按列名访问
- `_init_schema()` 在构造时调用，幂等（检查 schema_version 表是否存在）
- `transaction()` 上下文管理器保证事务完整性
- `read()` 上下文管理器用于只读查询

### db/schema.sql

从技术架构文档 3.2 节**完整复制** SQL，包括：
- `schema_version`
- `projects`（含 5 个阶段状态字段）
- `supplier_files`
- `raw_tables`
- `standardized_rows`
- `commodity_groups`
- `group_members`
- `comparison_results`
- `audit_logs`
- `requirement_items`
- `compliance_matches`
- 所有索引

**使用 `CREATE TABLE IF NOT EXISTS`** 保证幂等性。

### db/project_repo.py（骨架）

```python
from db.database import Database

class ProjectRepo:
    """项目表 CRUD 操作 — Task 0.4 填充实现"""

    def __init__(self, db: Database):
        self.db = db
```

### tests/test_database.py

```python
import os
import tempfile
import pytest
from db.database import Database

@pytest.fixture
def db_path():
    """临时数据库文件路径"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)

@pytest.fixture
def db(db_path):
    """初始化数据库实例"""
    return Database(db_path)

def test_schema_creates_all_tables(db):
    """schema 初始化应创建所有表"""
    expected_tables = {
        "schema_version", "projects", "supplier_files", "raw_tables",
        "standardized_rows", "commodity_groups", "group_members",
        "comparison_results", "audit_logs", "requirement_items",
        "compliance_matches",
    }
    with db.read() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        actual_tables = {row["name"] for row in cursor.fetchall()}
    assert expected_tables.issubset(actual_tables), f"缺少表: {expected_tables - actual_tables}"

def test_schema_is_idempotent(db_path):
    """重复初始化不应报错"""
    db1 = Database(db_path)
    db2 = Database(db_path)  # 第二次初始化不应出错
    with db2.read() as conn:
        cursor = conn.execute("SELECT count(*) as cnt FROM schema_version")
        assert cursor.fetchone()["cnt"] == 1

def test_foreign_keys_enabled(db):
    """PRAGMA foreign_keys 应为 ON"""
    with db.read() as conn:
        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1

def test_transaction_commit(db):
    """事务正常提交"""
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
            ("test-id-1", "测试项目"),
        )
    with db.read() as conn:
        cursor = conn.execute("SELECT name FROM projects WHERE id = ?", ("test-id-1",))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "测试项目"

def test_transaction_rollback(db):
    """事务异常回滚"""
    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
                ("test-id-2", "会被回滚的项目"),
            )
            raise ValueError("模拟异常")
    except ValueError:
        pass
    with db.read() as conn:
        cursor = conn.execute("SELECT name FROM projects WHERE id = ?", ("test-id-2",))
        assert cursor.fetchone() is None

def test_foreign_key_constraint(db):
    """外键约束生效"""
    with pytest.raises(Exception):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO supplier_files (id, project_id, supplier_name, original_filename, file_path, file_type, imported_at) "
                "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                ("file-1", "nonexistent-project", "供应商A", "test.xlsx", "source_files/test.xlsx", "xlsx"),
            )

def test_cascade_delete(db):
    """CASCADE 删除生效"""
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
            ("proj-del", "待删除项目"),
        )
        conn.execute(
            "INSERT INTO supplier_files (id, project_id, supplier_name, original_filename, file_path, file_type, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("file-del", "proj-del", "供应商A", "test.xlsx", "source_files/test.xlsx", "xlsx"),
        )
    with db.transaction() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", ("proj-del",))
    with db.read() as conn:
        cursor = conn.execute("SELECT id FROM supplier_files WHERE id = ?", ("file-del",))
        assert cursor.fetchone() is None, "CASCADE 删除未生效"

def test_stage_status_check_constraint(db):
    """阶段状态 CHECK 约束生效"""
    with pytest.raises(Exception):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, created_at, updated_at, import_status) "
                "VALUES (?, ?, datetime('now'), datetime('now'), ?)",
                ("proj-bad", "坏状态项目", "invalid_status"),
            )
```

## 测试与验收

```bash
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest tests/test_database.py -v       # 预期 8 个测试全部通过
```

**断言清单：**
- 11 张表全部创建成功
- schema 初始化幂等（重复调用不报错）
- `PRAGMA foreign_keys` 为 ON
- 事务 commit 后数据可读
- 事务 rollback 后数据不存在
- 外键约束拒绝无效引用
- CASCADE 删除级联生效
- CHECK 约束拒绝非法状态值

## 提交

```bash
git add backend/db/ backend/tests/test_database.py
git commit -m "Phase 0.3: SQLite 数据库层 — 连接管理 + 事务封装 + 完整 schema"
```
