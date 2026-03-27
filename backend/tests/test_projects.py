import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _use_temp_app_data(monkeypatch: pytest.MonkeyPatch, tmp_path):  # type: ignore[no-untyped-def]
    """使用临时目录作为应用数据目录"""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    import config
    from config import Settings

    config.settings = Settings()


@pytest.fixture
async def client():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_create_project(client: AsyncClient) -> None:
    resp = await client.post("/api/projects", json={"name": "测试项目A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试项目A"
    assert "id" in data
    assert "stage_statuses" in data
    assert data["stage_statuses"]["import_status"] == "pending"
    assert data["stage_statuses"]["compliance_status"] == "skipped"


@pytest.mark.anyio
async def test_create_project_empty_name(client: AsyncClient) -> None:
    resp = await client.post("/api/projects", json={"name": ""})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_list_projects_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_projects_after_create(client: AsyncClient) -> None:
    await client.post("/api/projects", json={"name": "项目1"})
    await client.post("/api/projects", json={"name": "项目2"})
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 最新的在前面
    assert data[0]["name"] == "项目2"


@pytest.mark.anyio
async def test_get_project(client: AsyncClient) -> None:
    create_resp = await client.post("/api/projects", json={"name": "详情项目"})
    project_id = create_resp.json()["id"]
    resp = await client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "详情项目"
    assert data["id"] == project_id


@pytest.mark.anyio
async def test_get_project_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/projects/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_project(client: AsyncClient) -> None:
    create_resp = await client.post("/api/projects", json={"name": "待删除"})
    project_id = create_resp.json()["id"]
    # 删除
    del_resp = await client.delete(f"/api/projects/{project_id}")
    assert del_resp.status_code == 200
    # 确认已删除
    get_resp = await client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 404
    # 列表中也不存在
    list_resp = await client.get("/api/projects")
    assert len(list_resp.json()) == 0


@pytest.mark.anyio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/api/projects/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_project_creates_directory_structure(client: AsyncClient, tmp_path) -> None:  # type: ignore[no-untyped-def]
    create_resp = await client.post("/api/projects", json={"name": "目录检查"})
    project_id = create_resp.json()["id"]
    project_dir = tmp_path / "projects" / project_id
    assert project_dir.exists()
    assert (project_dir / "project.db").exists()
    assert (project_dir / "source_files").is_dir()
    assert (project_dir / "exports").is_dir()
