import os
import sqlite3
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
def db(db_path: str) -> Database:
    """初始化数据库实例"""
    return Database(db_path)


def test_schema_creates_all_tables(db: Database) -> None:
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


def test_schema_is_idempotent(db_path: str) -> None:
    """重复初始化不应报错"""
    db1 = Database(db_path)
    db2 = Database(db_path)  # 第二次初始化不应出错
    assert db1 is not db2  # suppress unused variable warnings
    with db2.read() as conn:
        cursor = conn.execute("SELECT count(*) as cnt FROM schema_version")
        assert cursor.fetchone()["cnt"] == 1


def test_foreign_keys_enabled(db: Database) -> None:
    """PRAGMA foreign_keys 应为 ON"""
    with db.read() as conn:
        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1


def test_transaction_commit(db: Database) -> None:
    """事务正常提交"""
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) "
            "VALUES (?, ?, datetime('now'), datetime('now'))",
            ("test-id-1", "测试项目"),
        )
    with db.read() as conn:
        cursor = conn.execute("SELECT name FROM projects WHERE id = ?", ("test-id-1",))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "测试项目"


def test_transaction_rollback(db: Database) -> None:
    """事务异常回滚"""
    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, created_at, updated_at) "
                "VALUES (?, ?, datetime('now'), datetime('now'))",
                ("test-id-2", "会被回滚的项目"),
            )
            raise ValueError("模拟异常")
    except ValueError:
        pass
    with db.read() as conn:
        cursor = conn.execute("SELECT name FROM projects WHERE id = ?", ("test-id-2",))
        assert cursor.fetchone() is None


def test_foreign_key_constraint(db: Database) -> None:
    """外键约束生效"""
    with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
        conn.execute(
            "INSERT INTO supplier_files "
            "(id, project_id, supplier_name, original_filename, file_path, file_type, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("file-1", "nonexistent-project", "供应商A", "test.xlsx", "source_files/test.xlsx", "xlsx"),
        )


def test_cascade_delete(db: Database) -> None:
    """CASCADE 删除生效"""
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) "
            "VALUES (?, ?, datetime('now'), datetime('now'))",
            ("proj-del", "待删除项目"),
        )
        conn.execute(
            "INSERT INTO supplier_files "
            "(id, project_id, supplier_name, original_filename, file_path, file_type, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("file-del", "proj-del", "供应商A", "test.xlsx", "source_files/test.xlsx", "xlsx"),
        )
    with db.transaction() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", ("proj-del",))
    with db.read() as conn:
        cursor = conn.execute("SELECT id FROM supplier_files WHERE id = ?", ("file-del",))
        assert cursor.fetchone() is None, "CASCADE 删除未生效"


def test_stage_status_check_constraint(db: Database) -> None:
    """阶段状态 CHECK 约束生效"""
    with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at, import_status) "
            "VALUES (?, ?, datetime('now'), datetime('now'), ?)",
            ("proj-bad", "坏状态项目", "invalid_status"),
        )
