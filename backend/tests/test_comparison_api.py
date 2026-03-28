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
    resp = await client.post("/api/projects", json={"name": "比价测试项目"})
    assert resp.status_code == 200
    pid: str = resp.json()["id"]
    return pid


def _insert_group_with_rows(
    project_id: str,
    *,
    supplier_count: int = 3,
    with_requirements: bool = False,
) -> dict:
    """在项目 DB 中插入已确认归组 + 供应商 + 标准化行 + group_members"""
    from api.deps import get_project_db

    db = get_project_db(project_id)
    group_id = str(uuid.uuid4())
    sf_ids: list[str] = []
    names = ["供应商A", "供应商B", "供应商C"]
    prices = [4299.0, 4599.0, 4199.0]

    with db.transaction() as conn:
        # 插入已确认归组
        conn.execute(
            """INSERT INTO commodity_groups
               (id, project_id, group_name, normalized_key,
                confidence_level, match_score, match_reason, status, confirmed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, project_id, "笔记本电脑", "notebook",
             "high", 0.95, "完全匹配", "confirmed", "2026-01-01T00:00:00Z"),
        )

        for i in range(supplier_count):
            sf_id = f"sf-{i + 1}"
            sf_ids.append(sf_id)
            conn.execute(
                """INSERT OR IGNORE INTO supplier_files
                   (id, project_id, supplier_name, original_filename, file_path, file_type, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sf_id, project_id, names[i], f"file{i}.xlsx",
                 f"/tmp/file{i}.xlsx", "xlsx", "2026-01-01T00:00:00Z"),
            )

            rt_id = f"rt-{i + 1}"
            conn.execute(
                """INSERT OR IGNORE INTO raw_tables
                   (id, supplier_file_id, table_index, row_count, column_count, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rt_id, sf_id, 0, 1, 5, "[]"),
            )

            sr_id = f"sr-{i + 1}"
            conn.execute(
                """INSERT INTO standardized_rows
                   (id, raw_table_id, supplier_file_id, row_index, product_name, spec_model,
                    unit, quantity, unit_price, total_price, tax_basis,
                    source_location, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sr_id, rt_id, sf_id, 0, "ThinkPad E14", "i7/16GB/512GB",
                 "台", 10, prices[i], prices[i] * 10,
                 "含税", "{}", 1.0),
            )

            conn.execute(
                """INSERT INTO group_members
                   (group_id, standardized_row_id)
                   VALUES (?, ?)""",
                (group_id, sr_id),
            )

    if with_requirements:
        from db.compliance_repo import ComplianceRepo
        from db.requirement_repo import RequirementRepo

        req_repo = RequirementRepo(db)
        req_id = str(uuid.uuid4())
        req_repo.insert(
            req_id=req_id, project_id=project_id, code="REQ-001",
            category="技术规格", title="内存>=16GB",
            description=None, is_mandatory=True, match_type="numeric",
            expected_value="16", operator="gte", sort_order=1,
        )

        comp_repo = ComplianceRepo(db)
        # sf-1 和 sf-2 符合需求，sf-3 不符合
        for j, sf_id in enumerate(sf_ids):
            status = "match" if j < 2 else "no_match"
            comp_repo.insert(
                match_id=str(uuid.uuid4()),
                requirement_item_id=req_id,
                commodity_group_id=group_id,
                supplier_file_id=sf_id,
                status=status,
                is_acceptable=j < 2,
                match_score=1.0 if j < 2 else 0.0,
                evidence_text="16GB 内存" if j < 2 else "8GB",
                evidence_location="{}",
                match_method="numeric",
                needs_review=False,
                engine_versions="{}",
            )

    return {"group_id": group_id, "sf_ids": sf_ids}


@pytest.fixture
def _setup_groups(project_id: str) -> dict:  # type: ignore[no-untyped-def]
    return _insert_group_with_rows(project_id)


@pytest.fixture
def _setup_groups_with_req(project_id: str) -> dict:  # type: ignore[no-untyped-def]
    return _insert_group_with_rows(project_id, with_requirements=True)


class TestComparisonAPI:
    @pytest.mark.anyio
    async def test_generate_returns_task_id(
        self, client, project_id: str, _setup_groups: dict
    ) -> None:
        resp = await client.post(
            f"/api/projects/{project_id}/comparison/generate",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "taskId" in data or "task_id" in data

    @pytest.mark.anyio
    async def test_get_comparison_empty(
        self, client, project_id: str, _setup_groups: dict
    ) -> None:
        """未生成比价时返回空列表"""
        resp = await client.get(
            f"/api/projects/{project_id}/comparison",
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_get_comparison_results(
        self, client, project_id: str, _setup_groups: dict
    ) -> None:
        """生成比价后获取结果，验证字段完整性"""
        # 先同步执行 generate（直接调用 service 而非异步任务）
        from api.deps import get_project_db
        from services.comparison_service import ComparisonService

        db = get_project_db(project_id)
        service = ComparisonService(db)
        service.generate_comparison(project_id)

        resp = await client.get(
            f"/api/projects/{project_id}/comparison",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        r = data[0]
        assert r["comparisonStatus"] in ("comparable", "blocked", "partial")
        assert "minPrice" in r
        assert "effectiveMinPrice" in r
        assert "supplierPrices" in r
        assert isinstance(r["supplierPrices"], list)
        assert "anomalyDetails" in r
        assert "groupName" in r

    @pytest.mark.anyio
    async def test_comparison_without_requirements(
        self, client, project_id: str, _setup_groups: dict
    ) -> None:
        """无需求标准时 effectiveMinPrice == minPrice"""
        from api.deps import get_project_db
        from services.comparison_service import ComparisonService

        db = get_project_db(project_id)
        service = ComparisonService(db)
        service.generate_comparison(project_id)

        resp = await client.get(
            f"/api/projects/{project_id}/comparison",
        )
        data = resp.json()
        for r in data:
            assert r["effectiveMinPrice"] == r["minPrice"]

    @pytest.mark.anyio
    async def test_comparison_with_requirements_effective_min(
        self, client, project_id: str, _setup_groups_with_req: dict
    ) -> None:
        """有需求标准时 effectiveMinPrice 仅基于符合需求的供应商"""
        from api.deps import get_project_db
        from services.comparison_service import ComparisonService

        db = get_project_db(project_id)
        service = ComparisonService(db)
        service.generate_comparison(project_id)

        resp = await client.get(
            f"/api/projects/{project_id}/comparison",
        )
        data = resp.json()
        assert len(data) > 0
        r = data[0]
        # minPrice=4199 (sf-3 惠普), effectiveMinPrice=4299 (sf-1 联想, sf-3 不合规)
        assert r["minPrice"] == 4199.0
        assert r["effectiveMinPrice"] == 4299.0

    @pytest.mark.anyio
    async def test_comparison_status_updated(
        self, client, project_id: str, _setup_groups: dict
    ) -> None:
        """比价完成后 comparison_status 变为 completed"""
        from api.deps import get_project_db
        from services.comparison_service import ComparisonService

        db = get_project_db(project_id)
        service = ComparisonService(db)
        service.generate_comparison(project_id)

        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        stage_statuses = data.get("stageStatuses", data.get("stage_statuses", {}))
        comparison = stage_statuses.get(
            "comparisonStatus", stage_statuses.get("comparison_status")
        )
        assert comparison == "completed"

    @pytest.mark.anyio
    async def test_generate_no_groups_returns_422(
        self, client, project_id: str
    ) -> None:
        """[M10] 无已确认归组时返回 422"""
        resp = await client.post(
            f"/api/projects/{project_id}/comparison/generate",
        )
        assert resp.status_code == 422
