from datetime import UTC

import pytest

from db.database import Database
from db.file_repo import FileRepo
from db.table_repo import TableRepo


@pytest.fixture
def db(tmp_path):  # type: ignore[no-untyped-def]
    database = Database(tmp_path / "test.db")
    return database


@pytest.fixture
def file_repo(db):  # type: ignore[no-untyped-def]
    return FileRepo(db)


@pytest.fixture
def table_repo(db):  # type: ignore[no-untyped-def]
    return TableRepo(db)


@pytest.fixture
def setup_file(db, file_repo):  # type: ignore[no-untyped-def]
    from datetime import datetime
    now = datetime.now(UTC).isoformat()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("p1", "test", now, now),
        )
    file_repo.insert("f1", "p1", "供应商A", "test.xlsx",
                     "source_files/f1.xlsx", "xlsx", "structure")


def test_insert_and_get(table_repo: TableRepo, setup_file: None) -> None:
    result = table_repo.insert("t1", "f1", 0, "Sheet1", None, 10, 3,
                               {"headers": ["A", "B", "C"], "rows": []})
    assert result["id"] == "t1"
    assert result["selected"] == 1


def test_toggle_selection(table_repo: TableRepo, setup_file: None) -> None:
    table_repo.insert("t1", "f1", 0, "Sheet1", None, 10, 3,
                      {"headers": [], "rows": []})
    result = table_repo.toggle_selection("t1")
    assert result is not None
    assert result["selected"] == 0
    result = table_repo.toggle_selection("t1")
    assert result is not None
    assert result["selected"] == 1


def test_list_by_file(table_repo: TableRepo, setup_file: None) -> None:
    table_repo.insert("t1", "f1", 0, "Sheet1", None, 5, 3,
                      {"headers": [], "rows": []})
    table_repo.insert("t2", "f1", 1, "Sheet2", None, 8, 4,
                      {"headers": [], "rows": []})
    result = table_repo.list_by_file("f1")
    assert len(result) == 2
    assert result[0]["table_index"] == 0


def test_list_by_project(table_repo: TableRepo, setup_file: None) -> None:
    table_repo.insert("t1", "f1", 0, "Sheet1", None, 5, 3,
                      {"headers": [], "rows": []})
    result = table_repo.list_by_project("p1")
    assert len(result) == 1
    assert result[0]["supplier_name"] == "供应商A"


def test_raw_data_deserialized_as_dict(table_repo: TableRepo, setup_file: None) -> None:
    """B3: raw_data 读出后应为 dict，不是 JSON 字符串"""
    raw = {"headers": ["品名", "单价"], "rows": [["笔", "5"]]}
    table_repo.insert("t1", "f1", 0, "Sheet1", None, 1, 2, raw)

    # get_by_id
    row = table_repo.get_by_id("t1")
    assert row is not None
    assert isinstance(row["raw_data"], dict)
    assert row["raw_data"] == raw

    # list_by_file
    rows = table_repo.list_by_file("f1")
    assert isinstance(rows[0]["raw_data"], dict)

    # list_by_project
    rows = table_repo.list_by_project("p1")
    assert isinstance(rows[0]["raw_data"], dict)
