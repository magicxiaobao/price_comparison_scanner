from datetime import UTC

import pytest

from db.database import Database
from db.file_repo import FileRepo


@pytest.fixture
def db(tmp_path):  # type: ignore[no-untyped-def]
    database = Database(tmp_path / "test.db")
    return database


@pytest.fixture
def repo(db):  # type: ignore[no-untyped-def]
    # Insert a project first (foreign key constraint)
    from datetime import datetime
    now = datetime.now(UTC).isoformat()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("p1", "test", now, now),
        )
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("p2", "test2", now, now),
        )
    return FileRepo(db)


def test_insert_and_get(repo: FileRepo) -> None:
    result = repo.insert("f1", "p1", "供应商A", "test.xlsx",
                         "source_files/f1.xlsx", "xlsx", "structure")
    assert result["id"] == "f1"
    assert result["supplier_name"] == "供应商A"
    assert result["supplier_confirmed"] == 0

    got = repo.get_by_id("f1")
    assert got is not None
    assert got["project_id"] == "p1"


def test_confirm_supplier(repo: FileRepo) -> None:
    repo.insert("f1", "p1", "猜测名", "test.xlsx",
                "source_files/f1.xlsx", "xlsx", "structure")
    result = repo.confirm_supplier("f1", "真实供应商")
    assert result is not None
    assert result["supplier_name"] == "真实供应商"
    assert result["supplier_confirmed"] == 1


def test_list_by_project(repo: FileRepo) -> None:
    repo.insert("f1", "p1", "A", "a.xlsx", "source_files/f1.xlsx", "xlsx", "structure")
    repo.insert("f2", "p1", "B", "b.xlsx", "source_files/f2.xlsx", "xlsx", "structure")
    repo.insert("f3", "p2", "C", "c.xlsx", "source_files/f3.xlsx", "xlsx", "structure")
    result = repo.list_by_project("p1")
    assert len(result) == 2


def test_delete(repo: FileRepo) -> None:
    repo.insert("f1", "p1", "A", "a.xlsx", "source_files/f1.xlsx", "xlsx", "structure")
    assert repo.delete("f1") is True
    assert repo.get_by_id("f1") is None
    assert repo.delete("nonexistent") is False


def test_update_recognition_mode(repo: FileRepo) -> None:
    repo.insert("f1", "p1", "A", "a.xlsx", "source_files/f1.xlsx", "xlsx", "structure")
    repo.update_recognition_mode("f1", "manual")
    got = repo.get_by_id("f1")
    assert got is not None
    assert got["recognition_mode"] == "manual"
