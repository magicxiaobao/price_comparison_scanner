
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
def sample_xlsx(tmp_path):  # type: ignore[no-untyped-def]
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "报价"
    ws.append(["商品", "单价", "数量"])
    ws.append(["电脑", "5000", "10"])
    path = tmp_path / "联想_报价单.xlsx"
    wb.save(path)
    return path


@pytest.mark.anyio
async def test_upload_file(client, sample_xlsx) -> None:  # type: ignore[no-untyped-def]
    """上传文件 -> 返回 file_id + task_id"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    with open(sample_xlsx, "rb") as f:
        resp = await client.post(
            f"/api/projects/{project_id}/files",
            files={"file": ("联想_报价单.xlsx", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data
    assert "task_id" in data
    assert "supplier_name_guess" in data


@pytest.mark.anyio
async def test_upload_unsupported_type(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """上传不支持的文件类型 -> 400"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    txt_file = tmp_path / "test.txt"
    txt_file.write_text("hello")
    with open(txt_file, "rb") as f:
        resp = await client.post(
            f"/api/projects/{project_id}/files",
            files={"file": ("test.txt", f, "text/plain")},
        )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_upload_to_nonexistent_project(client, sample_xlsx) -> None:  # type: ignore[no-untyped-def]
    """上传到不存在的项目 -> 404"""
    with open(sample_xlsx, "rb") as f:
        resp = await client.post(
            "/api/projects/nonexistent/files",
            files={"file": ("test.xlsx", f, "application/octet-stream")},
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_confirm_supplier(client, sample_xlsx) -> None:  # type: ignore[no-untyped-def]
    """确认供应商名称"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    with open(sample_xlsx, "rb") as f:
        upload_resp = await client.post(
            f"/api/projects/{project_id}/files",
            files={"file": ("联想_报价单.xlsx", f, "application/octet-stream")},
        )
    file_id = upload_resp.json()["file_id"]

    resp = await client.put(
        f"/api/files/{file_id}/confirm-supplier",
        json={"supplier_name": "联想集团", "project_id": project_id},
    )
    assert resp.status_code == 200
    assert resp.json()["supplier_confirmed"] is True
    assert resp.json()["supplier_name"] == "联想集团"


@pytest.mark.anyio
async def test_list_files(client, sample_xlsx) -> None:  # type: ignore[no-untyped-def]
    """获取项目的文件列表"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    with open(sample_xlsx, "rb") as f:
        await client.post(
            f"/api/projects/{project_id}/files",
            files={"file": ("联想_报价单.xlsx", f, "application/octet-stream")},
        )

    resp = await client.get(f"/api/projects/{project_id}/files")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.anyio
async def test_list_tables_empty(client) -> None:  # type: ignore[no-untyped-def]
    """项目无文件时 -> 空表格列表"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    resp = await client.get(f"/api/projects/{project_id}/tables")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_confirm_supplier_invalid_project(client, sample_xlsx) -> None:  # type: ignore[no-untyped-def]
    """确认供应商 - 传入不存在的 project_id -> 404"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    with open(sample_xlsx, "rb") as f:
        upload_resp = await client.post(
            f"/api/projects/{project_id}/files",
            files={"file": ("联想_报价单.xlsx", f, "application/octet-stream")},
        )
    file_id = upload_resp.json()["file_id"]

    resp = await client.put(
        f"/api/files/{file_id}/confirm-supplier",
        json={"supplier_name": "联想集团", "project_id": "nonexistent"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "项目不存在"


@pytest.mark.anyio
async def test_toggle_table_selection_invalid_project(client) -> None:  # type: ignore[no-untyped-def]
    """切换表格选中状态 - 传入不存在的 project_id -> 404"""
    resp = await client.put(
        "/api/tables/some-table-id/toggle-selection",
        json={"project_id": "nonexistent"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "项目不存在"


@pytest.mark.anyio
async def test_guess_supplier_name() -> None:
    """供应商名称猜测规则"""
    from services.file_service import FileService

    guess = FileService._guess_supplier_name
    assert guess("联想_报价单.xlsx") == "联想"
    assert guess("华为报价.docx") == "华为"
    assert guess("Dell_报价表_2024-01-15.pdf") == "Dell"
    assert guess("报价单.xlsx") == "未知供应商"
