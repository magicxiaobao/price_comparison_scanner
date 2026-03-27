from collections.abc import Generator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from db.database import Database


@pytest.fixture(params=["asyncio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """
    每个测试独立的 settings 实例。
    测试默认运行在非 DEV_MODE，需要 token。
    fixture 结束后自动恢复原始 settings（通过 monkeypatch 的自动清理）。
    """
    monkeypatch.setenv("DEV_MODE", "")
    monkeypatch.setenv("SESSION_TOKEN", "test-token-abc")
    # 重新加载 config 使环境变量生效
    import config
    from config import Settings

    original = config.settings
    config.settings = Settings()
    yield
    # monkeypatch 自动恢复环境变量，这里显式恢复 settings 对象
    config.settings = original


@pytest.fixture
async def client():
    """无认证的测试客户端"""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def authed_client():
    """带认证 token 的测试客户端"""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token-abc"},
    ) as c:
        yield c


@pytest.fixture
def project_db(tmp_path: Path) -> Database:
    """创建临时项目数据库，初始化完整 schema，插入测试项目"""
    db_path = tmp_path / "test_project.db"
    # 手动创建不触发 _init_schema（因为 schema.sql 路径在 db/ 下）
    import sqlite3

    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("p1", "test-project", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    # 创建 Database 实例（会跳过 schema init 因为 schema_version 已存在）
    return Database(db_path)


@pytest.fixture
def sample_standardized_rows(project_db: Database) -> list[dict]:
    """插入 3 条测试用标准化行，返回行记录列表"""
    rows = []
    with project_db.transaction() as conn:
        conn.execute(
            """INSERT INTO supplier_files
               (id, project_id, original_filename, file_path, file_type, supplier_name, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("sf1", "p1", "test.xlsx", "/tmp/test.xlsx", "xlsx", "供应商A", "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            """INSERT INTO raw_tables
               (id, supplier_file_id, table_index, sheet_name, row_count, column_count, raw_data, selected)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("rt1", "sf1", 0, "Sheet1", 3, 5, "[]", 1),
        )
        for i in range(3):
            row_id = f"sr{i + 1}"
            conn.execute(
                """INSERT INTO standardized_rows
                   (id, raw_table_id, supplier_file_id, row_index, product_name, spec_model, unit,
                    quantity, unit_price, source_location)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row_id, "rt1", "sf1", i, f"商品{i + 1}", f"规格{i + 1}", "台", 10.0, 100.0, "{}"),
            )
            rows.append({
                "id": row_id,
                "product_name": f"商品{i + 1}",
                "spec_model": f"规格{i + 1}",
                "unit": "台",
            })
    return rows
