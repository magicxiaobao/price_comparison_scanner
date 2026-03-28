from __future__ import annotations

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
    resp = await client.post("/api/projects", json={"name": "测试项目"})
    assert resp.status_code == 200
    pid: str = resp.json()["id"]
    return pid


@pytest.fixture
async def first_req_id(client, project_id: str) -> str:  # type: ignore[no-untyped-def]
    resp = await client.post(
        f"/api/projects/{project_id}/requirements",
        json={"category": "技术规格", "title": "内存>=16GB", "matchType": "numeric",
              "expectedValue": "16", "operator": "gte"},
    )
    assert resp.status_code == 200
    rid: str = resp.json()["id"]
    return rid


class TestRequirementsAPI:
    @pytest.mark.anyio
    async def test_create_requirement(self, client, project_id: str) -> None:
        resp = await client.post(
            f"/api/projects/{project_id}/requirements",
            json={
                "category": "技术规格",
                "title": "内存>=16GB",
                "matchType": "numeric",
                "expectedValue": "16",
                "operator": "gte",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "内存>=16GB"
        assert data["matchType"] == "numeric"
        assert data["code"].startswith("REQ-")

    @pytest.mark.anyio
    async def test_list_requirements(self, client, project_id: str, first_req_id: str) -> None:
        resp = await client.get(f"/api/projects/{project_id}/requirements")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.anyio
    async def test_update_requirement(self, client, project_id: str, first_req_id: str) -> None:
        resp = await client.put(
            f"/api/requirements/{first_req_id}",
            json={"projectId": project_id, "title": "修改后标题"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "修改后标题"

    @pytest.mark.anyio
    async def test_delete_requirement(self, client, project_id: str, first_req_id: str) -> None:
        resp = await client.delete(
            f"/api/requirements/{first_req_id}",
            params={"project_id": project_id},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, client, project_id: str) -> None:
        resp = await client.delete(
            "/api/requirements/nonexistent",
            params={"project_id": project_id},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_compliance_stage_activation(self, client, project_id: str) -> None:
        """创建需求项后 compliance_status 从 skipped 变为 pending"""
        await client.post(
            f"/api/projects/{project_id}/requirements",
            json={"category": "功能要求", "title": "test", "matchType": "manual"},
        )
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        stage_statuses = data.get("stageStatuses", data.get("stage_statuses", {}))
        compliance = stage_statuses.get("complianceStatus", stage_statuses.get("compliance_status"))
        assert compliance != "skipped"

    @pytest.mark.anyio
    async def test_invalid_category(self, client, project_id: str) -> None:
        resp = await client.post(
            f"/api/projects/{project_id}/requirements",
            json={"category": "无效分类", "title": "test", "matchType": "manual"},
        )
        assert resp.status_code == 422
