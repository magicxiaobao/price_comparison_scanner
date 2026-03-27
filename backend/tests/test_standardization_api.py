"""Task 2.5: 标准化 API + 手工修正 + 失效传播 测试"""
from __future__ import annotations

import time
import uuid
from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _use_temp_app_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> Generator[None, None, None]:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("SESSION_TOKEN", "")
    import config
    from config import Settings

    original = config.settings
    config.settings = Settings()
    yield
    config.settings = original


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


def _setup_project_with_raw_data(tmp_path: object) -> tuple[str, str, str]:
    """
    创建项目 + supplier_file + raw_table，返回 (project_id, raw_table_id, supplier_file_id)。
    """
    from config import get_app_data_dir
    from db.database import Database
    from db.file_repo import FileRepo
    from db.table_repo import TableRepo
    from models.project import ProjectCreate
    from services.project_service import ProjectService

    svc = ProjectService()
    project = svc.create_project(ProjectCreate(name="测试项目"))
    project_id = project.id

    project_dir = get_app_data_dir() / "projects" / project_id
    db = Database(project_dir / "project.db")

    file_id = str(uuid.uuid4())
    file_repo = FileRepo(db)
    file_repo.insert(
        file_id=file_id,
        project_id=project_id,
        supplier_name="测试供应商",
        original_filename="test.xlsx",
        file_path=f"source_files/{file_id}.xlsx",
        file_type="xlsx",
        recognition_mode="structure",
    )

    table_id = str(uuid.uuid4())
    table_repo = TableRepo(db)
    raw_data = {
        "headers": ["产品名称", "规格型号", "单位", "数量", "单价"],
        "rows": [
            ["打印机", "HP-200", "台", 5, 3000],
            ["电脑", "Dell-500", "台", 10, 6000],
        ],
    }
    table_repo.insert(
        table_id=table_id,
        supplier_file_id=file_id,
        table_index=0,
        sheet_name="Sheet1",
        page_number=None,
        row_count=2,
        column_count=5,
        raw_data=raw_data,
    )

    return project_id, table_id, file_id


# ---- 标准化执行 ----


@pytest.mark.anyio
async def test_standardize_basic(client: AsyncClient, tmp_path: object) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    resp = await client.post(f"/api/projects/{project_id}/standardize")
    assert resp.status_code == 200
    data = resp.json()
    assert "taskId" in data
    assert data["taskId"]


@pytest.mark.anyio
async def test_standardize_creates_rows(client: AsyncClient, tmp_path: object) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)

    resp = await client.post(f"/api/projects/{project_id}/standardize")
    assert resp.status_code == 200
    task_id = resp.json()["taskId"]

    # 等待异步任务完成
    for _ in range(50):
        status_resp = await client.get(f"/api/tasks/{task_id}/status")
        if status_resp.json().get("status") in ("completed", "failed"):
            break
        time.sleep(0.1)

    assert status_resp.json()["status"] == "completed"

    rows_resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    assert rows_resp.status_code == 200
    rows = rows_resp.json()
    assert len(rows) == 2
    assert rows[0]["productName"] is not None


@pytest.mark.anyio
async def test_standardize_force(client: AsyncClient, tmp_path: object) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)

    # 第一次标准化
    resp1 = await client.post(f"/api/projects/{project_id}/standardize")
    task_id1 = resp1.json()["taskId"]
    for _ in range(50):
        s = await client.get(f"/api/tasks/{task_id1}/status")
        if s.json().get("status") in ("completed", "failed"):
            break
        time.sleep(0.1)

    # force=True 重新标准化
    resp2 = await client.post(
        f"/api/projects/{project_id}/standardize",
        json={"force": True},
    )
    task_id2 = resp2.json()["taskId"]
    for _ in range(50):
        s = await client.get(f"/api/tasks/{task_id2}/status")
        if s.json().get("status") in ("completed", "failed"):
            break
        time.sleep(0.1)

    rows_resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    rows = rows_resp.json()
    # force 后仍然是 2 行（不是 4 行重复）
    assert len(rows) == 2


# ---- 获取结果 ----


@pytest.mark.anyio
async def test_get_standardized_rows_empty(
    client: AsyncClient, tmp_path: object
) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_get_standardized_rows_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/projects/nonexistent/standardized-rows")
    assert resp.status_code == 404


# ---- 手工修正 ----


def _run_standardize_sync(project_id: str) -> None:
    """同步执行标准化（测试辅助）"""
    from services.project_service import ProjectService

    svc = ProjectService()
    task_id = svc.run_standardization(project_id)

    from engines.task_manager import get_task_manager

    tm = get_task_manager()
    for _ in range(100):
        info = tm.get_status(task_id)
        if info and info.status.value in ("completed", "failed"):
            break
        time.sleep(0.05)


@pytest.mark.anyio
async def test_modify_field_success(client: AsyncClient, tmp_path: object) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    _run_standardize_sync(project_id)

    rows_resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    rows = rows_resp.json()
    row_id = rows[0]["id"]

    resp = await client.put(
        f"/api/standardized-rows/{row_id}",
        json={"field": "unit_price", "newValue": 9999},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "auditLog" in data
    assert data["auditLog"]["field_name"] == "unit_price"


@pytest.mark.anyio
async def test_modify_field_audit_log(client: AsyncClient, tmp_path: object) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    _run_standardize_sync(project_id)

    rows_resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    row_id = rows_resp.json()[0]["id"]

    await client.put(
        f"/api/standardized-rows/{row_id}",
        json={"field": "unit_price", "newValue": 8888},
    )

    # 验证 audit_logs 有记录
    from config import get_app_data_dir
    from db.database import Database
    from services.audit_log_service import AuditLogService

    project_dir = get_app_data_dir() / "projects" / project_id
    db = Database(project_dir / "project.db")
    audit_svc = AuditLogService(db)
    logs = audit_svc.get_target_logs(row_id)
    assert len(logs) >= 1
    assert logs[0]["action_type"] == "modify_field"
    assert logs[0]["field_name"] == "unit_price"


@pytest.mark.anyio
async def test_modify_field_propagate_dirty(
    client: AsyncClient, tmp_path: object
) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    _run_standardize_sync(project_id)

    rows_resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    row_id = rows_resp.json()[0]["id"]

    resp = await client.put(
        f"/api/standardized-rows/{row_id}",
        json={"field": "unit_price", "newValue": 7777},
    )
    data = resp.json()
    assert "grouping" in data["dirtyStages"]
    assert "comparison" in data["dirtyStages"]


@pytest.mark.anyio
async def test_modify_field_invalid(client: AsyncClient, tmp_path: object) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    _run_standardize_sync(project_id)

    rows_resp = await client.get(f"/api/projects/{project_id}/standardized-rows")
    row_id = rows_resp.json()[0]["id"]

    resp = await client.put(
        f"/api/standardized-rows/{row_id}",
        json={"field": "invalid_field", "newValue": "xxx"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_modify_field_not_found(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/standardized-rows/nonexistent",
        json={"field": "unit_price", "newValue": 100},
    )
    assert resp.status_code == 404


# ---- 失效传播 ----


def test_propagate_dirty_from_normalize(tmp_path: object) -> None:
    from config import get_app_data_dir
    from db.database import Database
    from services.project_service import ProjectService

    project_id, _, _ = _setup_project_with_raw_data(tmp_path)

    project_dir = get_app_data_dir() / "projects" / project_id
    db = Database(project_dir / "project.db")

    svc = ProjectService()
    dirty = svc._propagate_dirty(project_id, db, "normalize")
    assert "grouping" in dirty
    assert "comparison" in dirty

    # 验证数据库状态
    from db.project_repo import ProjectRepo

    repo = ProjectRepo(db)
    row = repo.get_by_id(project_id)
    assert row is not None
    assert row["grouping_status"] == "dirty"
    assert row["comparison_status"] == "dirty"


def test_propagate_dirty_skip_skipped(tmp_path: object) -> None:
    from config import get_app_data_dir
    from db.database import Database
    from db.project_repo import ProjectRepo
    from services.project_service import ProjectService

    project_id, _, _ = _setup_project_with_raw_data(tmp_path)

    project_dir = get_app_data_dir() / "projects" / project_id
    db = Database(project_dir / "project.db")

    # compliance_status 默认是 skipped
    repo = ProjectRepo(db)
    row = repo.get_by_id(project_id)
    assert row is not None
    assert row["compliance_status"] == "skipped"

    svc = ProjectService()
    dirty = svc._propagate_dirty(project_id, db, "normalize")
    assert "compliance" not in dirty

    # 验证 compliance_status 仍为 skipped
    row = repo.get_by_id(project_id)
    assert row is not None
    assert row["compliance_status"] == "skipped"


# ---- 列名映射信息 ----


@pytest.mark.anyio
async def test_get_column_mapping_info(
    client: AsyncClient, tmp_path: object
) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    _run_standardize_sync(project_id)

    resp = await client.get(f"/api/projects/{project_id}/column-mapping-info")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


# ---- 异步任务集成 ----


@pytest.mark.anyio
async def test_standardize_task_status(
    client: AsyncClient, tmp_path: object
) -> None:
    project_id, _, _ = _setup_project_with_raw_data(tmp_path)
    resp = await client.post(f"/api/projects/{project_id}/standardize")
    task_id = resp.json()["taskId"]

    status_resp = await client.get(f"/api/tasks/{task_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "status" in status_data


# ---- 端点可达性 ----


@pytest.mark.anyio
async def test_standardize_not_found(client: AsyncClient) -> None:
    resp = await client.post("/api/projects/nonexistent/standardize")
    assert resp.status_code == 404
