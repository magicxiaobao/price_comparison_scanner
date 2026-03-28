from __future__ import annotations

import uuid

import pytest

import config
from config import Settings


@pytest.fixture(autouse=True)
def _use_temp_app_data(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("SESSION_TOKEN", "")
    config.settings = Settings()


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def project_id(client) -> str:  # type: ignore[no-untyped-def]
    resp = await client.post("/api/projects", json={"name": "导出测试项目"})
    assert resp.status_code == 200
    pid: str = resp.json()["id"]
    return pid


@pytest.fixture
def _setup_comparison_data(project_id: str) -> None:  # type: ignore[no-untyped-def]
    """插入归组 + 供应商 + 标准化行 + 比价结果"""
    from api.deps import get_project_db

    db = get_project_db(project_id)
    group_id = str(uuid.uuid4())
    sf_id = "sf-export-1"

    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO commodity_groups
               (id, project_id, group_name, normalized_key,
                confidence_level, match_score, match_reason, status, confirmed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, project_id, "测试商品", "test",
             "high", 0.95, "完全匹配", "confirmed", "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            """INSERT INTO supplier_files
               (id, project_id, supplier_name, original_filename, file_path, file_type, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sf_id, project_id, "供应商A", "test.xlsx", "/tmp/test.xlsx", "xlsx", "2026-01-01T00:00:00Z"),
        )
        rt_id = "rt-export-1"
        conn.execute(
            """INSERT INTO raw_tables
               (id, supplier_file_id, table_index, row_count, column_count, raw_data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rt_id, sf_id, 0, 1, 5, "[]"),
        )
        sr_id = "sr-export-1"
        conn.execute(
            """INSERT INTO standardized_rows
               (id, raw_table_id, supplier_file_id, row_index, product_name, spec_model,
                unit, quantity, unit_price, total_price, source_location, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sr_id, rt_id, sf_id, 0, "测试商品", "规格A",
             "台", 10, 100.0, 1000.0, "{}", 1.0),
        )
        conn.execute(
            """INSERT INTO group_members (group_id, standardized_row_id) VALUES (?, ?)""",
            (group_id, sr_id),
        )

    # 同步生成比价结果
    from services.comparison_service import ComparisonService

    service = ComparisonService(db)
    service.generate_comparison(project_id)


class TestExportAPI:
    @pytest.mark.anyio
    async def test_export_returns_task_id(
        self, client, project_id: str, _setup_comparison_data: None
    ) -> None:
        resp = await client.post(
            f"/api/projects/{project_id}/export",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "taskId" in data or "task_id" in data
