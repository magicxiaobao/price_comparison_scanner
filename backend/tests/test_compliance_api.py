from __future__ import annotations

import uuid

import pytest

import config
from config import Settings
from db.compliance_repo import ComplianceRepo
from db.requirement_repo import RequirementRepo


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
    resp = await client.post("/api/projects", json={"name": "测试项目"})
    assert resp.status_code == 200
    pid: str = resp.json()["id"]
    return pid


@pytest.fixture
def _setup_compliance_data(project_id: str) -> dict:  # type: ignore[no-untyped-def]
    """在项目 DB 中插入需求项 + 归组 + 供应商 + 标准化行 + 匹配结果"""
    from api.deps import get_project_db

    db = get_project_db(project_id)

    # 插入供应商文件
    sf_id = "sf-test-1"
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO supplier_files
               (id, project_id, supplier_name, original_filename, file_path, file_type, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sf_id, project_id, "供应商A", "test.xlsx", "/tmp/test.xlsx", "xlsx", "2026-01-01T00:00:00Z"),
        )

    # 插入需求项
    req_repo = RequirementRepo(db)
    req_id = str(uuid.uuid4())
    req_repo.insert(
        req_id=req_id, project_id=project_id, code="REQ-001",
        category="技术规格", title="内存>=16GB",
        description=None, is_mandatory=True, match_type="numeric",
        expected_value="16", operator="gte", sort_order=1,
    )

    # 插入已确认归组
    group_id = str(uuid.uuid4())
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO commodity_groups
               (id, project_id, group_name, normalized_key,
                confidence_level, match_score, match_reason, status, confirmed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, project_id, "笔记本电脑", "notebook",
             "high", 0.95, "完全匹配", "confirmed", "2026-01-01T00:00:00Z"),
        )

    # 插入匹配结果
    comp_repo = ComplianceRepo(db)
    match_id_1 = str(uuid.uuid4())
    comp_repo.insert(
        match_id=match_id_1, requirement_item_id=req_id,
        commodity_group_id=group_id, supplier_file_id=sf_id,
        status="unclear", is_acceptable=False, match_score=0.0,
        evidence_text="需人工确认", evidence_location="{}",
        match_method="numeric", needs_review=True, engine_versions="{}",
    )

    match_id_2 = str(uuid.uuid4())
    comp_repo.insert(
        match_id=match_id_2, requirement_item_id=req_id,
        commodity_group_id=group_id, supplier_file_id=sf_id,
        status="partial", is_acceptable=False, match_score=0.5,
        evidence_text="部分符合", evidence_location="{}",
        match_method="keyword", needs_review=True, engine_versions="{}",
    )

    return {
        "match_id_1": match_id_1,
        "match_id_2": match_id_2,
        "req_id": req_id,
        "group_id": group_id,
        "sf_id": sf_id,
    }


class TestComplianceAPI:
    @pytest.mark.anyio
    async def test_evaluate_returns_task_id(
        self, client, project_id: str, _setup_compliance_data: dict
    ) -> None:
        resp = await client.post(
            f"/api/projects/{project_id}/compliance/evaluate",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "taskId" in data or "task_id" in data

    @pytest.mark.anyio
    async def test_get_matrix(
        self, client, project_id: str, _setup_compliance_data: dict
    ) -> None:
        resp = await client.get(
            f"/api/projects/{project_id}/compliance/matrix",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "supplierNames" in data or "supplier_names" in data
        rows_key = "rows"
        assert rows_key in data
        assert isinstance(data[rows_key], list)

    @pytest.mark.anyio
    async def test_confirm_match(
        self, client, project_id: str, _setup_compliance_data: dict
    ) -> None:
        match_id = _setup_compliance_data["match_id_1"]
        resp = await client.put(
            f"/api/compliance/{match_id}/confirm",
            json={"projectId": project_id, "status": "match"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "match"
        assert data["needs_review"] == 0

    @pytest.mark.anyio
    async def test_accept_match(
        self, client, project_id: str, _setup_compliance_data: dict
    ) -> None:
        match_id = _setup_compliance_data["match_id_2"]
        resp = await client.put(
            f"/api/compliance/{match_id}/accept",
            json={"projectId": project_id, "isAcceptable": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_acceptable"] == 1

    @pytest.mark.anyio
    async def test_confirm_nonexistent_match(
        self, client, project_id: str
    ) -> None:
        resp = await client.put(
            "/api/compliance/nonexistent/confirm",
            json={"projectId": project_id, "status": "match"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_dirty_propagation_after_confirm(
        self, client, project_id: str, _setup_compliance_data: dict
    ) -> None:
        """确认匹配结果后 comparison_status 变为 dirty"""
        match_id = _setup_compliance_data["match_id_1"]
        await client.put(
            f"/api/compliance/{match_id}/confirm",
            json={"projectId": project_id, "status": "match"},
        )
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        stage_statuses = data.get("stageStatuses", data.get("stage_statuses", {}))
        comparison = stage_statuses.get(
            "comparisonStatus", stage_statuses.get("comparison_status")
        )
        assert comparison == "dirty"

    @pytest.mark.anyio
    async def test_invalid_confirm_status(
        self, client, project_id: str, _setup_compliance_data: dict
    ) -> None:
        match_id = _setup_compliance_data["match_id_1"]
        resp = await client.put(
            f"/api/compliance/{match_id}/confirm",
            json={"projectId": project_id, "status": "invalid_status"},
        )
        assert resp.status_code == 422
