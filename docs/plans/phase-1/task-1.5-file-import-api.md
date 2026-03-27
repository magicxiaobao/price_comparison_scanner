# Task 1.5: 文件导入 API + 供应商确认 API + 表格选择 API

## 输入条件

- Task 1.1 完成（TaskManager 就绪）
- Task 1.2 完成（Excel 解析器就绪）
- Task 1.3 完成（Word 解析器就绪）
- Task 1.4 完成（PDF 解析器就绪）
- Task 1.6 完成（Pydantic 模型就绪）

### 既有接口契约（Phase 0 已实现，本 Task 直接使用）

- **`api/deps.py:get_app_data_dir() -> Path`**：返回 `Path(config.settings.APP_DATA_DIR)`，是全局数据目录。`FileService` 应从 `api.deps` import 此函数（与 `ProjectService` 的引用方式一致）。
- **`services/project_service.py:ProjectService.get_project(project_id: str) -> ProjectDetail | None`**：查询项目详情，项目不存在时返回 None。`api/files.py` 路由中用于校验项目存在性。
- **`api/deps.py:get_project_db(project_id: str) -> Database`**：获取项目级 SQLite 数据库实例。可在 service 层或 repo 层按需使用。

## 输出物

- 创建: `backend/db/file_repo.py`
- 创建: `backend/db/table_repo.py`
- 创建: `backend/services/file_service.py`
- 创建: `backend/api/files.py`
- 修改: `backend/main.py`（注册 files 路由）
- 创建: `backend/tests/test_file_repo.py`
- 创建: `backend/tests/test_table_repo.py`
- 创建: `backend/tests/test_file_api.py`

## 禁止修改

- 不修改 `backend/db/database.py`
- 不修改 `backend/db/schema.sql`
- 不修改 `backend/engines/document_parser.py`（已稳定）
- 不修改 `backend/engines/task_manager.py`（已稳定）
- 不修改 `backend/api/middleware.py`
- 不修改 `frontend/`

## 实现规格

**分层职责约束：**
- `FileRepo` / `TableRepo`：纯数据访问层，只做 SQL 操作
- `FileService`：业务编排层，负责文件复制、调用解析器、调用 TaskManager、写库
- `api/files.py`：路由层，仅做请求解析和响应组装

**service 层禁止直接执行 SQL 语句**，必须通过 repo 方法操作数据库。

### db/file_repo.py

```python
from datetime import datetime, timezone
from db.database import Database


class FileRepo:
    """supplier_files 表 CRUD"""

    def __init__(self, db: Database):
        self.db = db

    def insert(self, file_id: str, project_id: str, supplier_name: str,
               original_filename: str, file_path: str, file_type: str,
               recognition_mode: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO supplier_files
                   (id, project_id, supplier_name, supplier_confirmed,
                    original_filename, file_path, file_type, recognition_mode, imported_at)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (file_id, project_id, supplier_name, original_filename,
                 file_path, file_type, recognition_mode, now),
            )
        return self.get_by_id(file_id)

    def get_by_id(self, file_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM supplier_files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM supplier_files WHERE project_id = ? ORDER BY imported_at",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def confirm_supplier(self, file_id: str, supplier_name: str) -> dict | None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE supplier_files SET supplier_name = ?, supplier_confirmed = 1 WHERE id = ?",
                (supplier_name, file_id),
            )
        return self.get_by_id(file_id)

    def update_recognition_mode(self, file_id: str, mode: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE supplier_files SET recognition_mode = ? WHERE id = ?",
                (mode, file_id),
            )

    def delete(self, file_id: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM supplier_files WHERE id = ?", (file_id,))
            return cursor.rowcount > 0
```

### db/table_repo.py

```python
import json
from db.database import Database


class TableRepo:
    """raw_tables 表 CRUD"""

    def __init__(self, db: Database):
        self.db = db

    def insert(self, table_id: str, supplier_file_id: str, table_index: int,
               sheet_name: str | None, page_number: int | None,
               row_count: int, column_count: int, raw_data: dict) -> dict:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO raw_tables
                   (id, supplier_file_id, table_index, sheet_name, page_number,
                    row_count, column_count, raw_data, selected)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (table_id, supplier_file_id, table_index, sheet_name,
                 page_number, row_count, column_count, json.dumps(raw_data, ensure_ascii=False)),
            )
        return self.get_by_id(table_id)

    def get_by_id(self, table_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM raw_tables WHERE id = ?", (table_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        """通过 supplier_files 关联查询项目的所有表格"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT rt.*, sf.supplier_name, sf.original_filename, sf.supplier_confirmed
                   FROM raw_tables rt
                   JOIN supplier_files sf ON rt.supplier_file_id = sf.id
                   WHERE sf.project_id = ?
                   ORDER BY sf.imported_at, rt.table_index""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_by_file(self, supplier_file_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM raw_tables WHERE supplier_file_id = ? ORDER BY table_index",
                (supplier_file_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def toggle_selection(self, table_id: str) -> dict | None:
        """切换 selected 状态（0 ↔ 1）"""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE raw_tables SET selected = CASE WHEN selected = 1 THEN 0 ELSE 1 END WHERE id = ?",
                (table_id,),
            )
        return self.get_by_id(table_id)
```

### services/file_service.py

```python
import uuid
import shutil
import re
from pathlib import Path

from db.database import Database
from db.file_repo import FileRepo
from db.table_repo import TableRepo
from engines.document_parser import DocumentParser
from engines.task_manager import get_task_manager
from config import get_app_data_dir


class FileService:
    """文件导入业务编排"""

    def __init__(self):
        self._parser = DocumentParser()

    def import_file(self, project_id: str, original_filename: str,
                    file_content: bytes) -> dict:
        """
        导入文件：
        1. 复制到 source_files/ 目录
        2. 猜测供应商名称
        3. 在数据库中创建 supplier_file 记录
        4. 通过 TaskManager 提交异步解析任务
        5. 返回 {file_id, task_id, supplier_name_guess}
        """
        file_id = str(uuid.uuid4())
        suffix = Path(original_filename).suffix.lower().lstrip(".")

        # 校验文件类型
        if suffix not in DocumentParser.SUPPORTED_TYPES:
            raise ValueError(f"不支持的文件类型: {suffix}")

        # 复制文件到 source_files/
        project_dir = get_app_data_dir() / "projects" / project_id
        source_dir = project_dir / "source_files"
        source_dir.mkdir(parents=True, exist_ok=True)
        dest_path = source_dir / f"{file_id}.{suffix}"
        dest_path.write_bytes(file_content)

        # 猜测供应商名称
        supplier_guess = self._guess_supplier_name(original_filename)

        # 写数据库
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        file_repo.insert(
            file_id=file_id,
            project_id=project_id,
            supplier_name=supplier_guess,
            original_filename=original_filename,
            file_path=f"source_files/{file_id}.{suffix}",
            file_type=suffix,
            recognition_mode="structure",
        )

        # 提交异步解析任务
        tm = get_task_manager()
        task_id = tm.submit(
            "file_parse",
            self._parse_task,
            project_id, file_id, str(dest_path),
        )

        return {
            "file_id": file_id,
            "task_id": task_id,
            "supplier_name_guess": supplier_guess,
        }

    def _parse_task(self, progress_callback, project_id: str,
                    file_id: str, file_path: str) -> dict:
        """
        异步解析任务的执行体。
        解析文件 → 将 RawTableData 写入 raw_tables 表。
        PDF L1 未识别到表格时，标记 recognition_mode = "manual"。
        """
        tables = self._parser.parse(file_path, progress_callback)

        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        table_repo = TableRepo(db)

        # PDF L1 空结果处理：标记为手动处理
        if not tables and file_path.lower().endswith(".pdf"):
            file_repo.update_recognition_mode(file_id, "manual")
            return {"file_id": file_id, "table_count": 0, "table_ids": []}

        table_ids = []
        for t in tables:
            table_id = str(uuid.uuid4())
            raw_data = {"headers": t.headers, "rows": t.rows}
            table_repo.insert(
                table_id=table_id,
                supplier_file_id=file_id,
                table_index=t.table_index,
                sheet_name=t.sheet_name,
                page_number=t.page_number,
                row_count=t.row_count,
                column_count=t.column_count,
                raw_data=raw_data,
            )
            table_ids.append(table_id)

        return {"file_id": file_id, "table_count": len(table_ids), "table_ids": table_ids}

    def confirm_supplier(self, file_id: str, supplier_name: str,
                         project_id: str) -> dict | None:
        """确认供应商名称"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        return file_repo.confirm_supplier(file_id, supplier_name)

    def get_tables(self, project_id: str) -> list[dict]:
        """获取项目的所有解析表格"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        table_repo = TableRepo(db)
        return table_repo.list_by_project(project_id)

    def toggle_table_selection(self, table_id: str, project_id: str) -> dict | None:
        """切换表格参与比价状态"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        table_repo = TableRepo(db)
        return table_repo.toggle_selection(table_id)

    def get_files(self, project_id: str) -> list[dict]:
        """获取项目的所有文件"""
        project_dir = get_app_data_dir() / "projects" / project_id
        db = Database(project_dir / "project.db")
        file_repo = FileRepo(db)
        return file_repo.list_by_project(project_id)

    @staticmethod
    def _guess_supplier_name(filename: str) -> str:
        """
        根据文件名猜测供应商名称。
        规则：
        1. 去掉扩展名
        2. 去掉常见后缀（报价单、报价、报价表、价格表）
        3. 去掉日期模式（2024-01-01, 20240101）
        4. 去掉下划线和连字符前后的空白
        5. 返回剩余部分作为猜测
        6. 如果为空，返回 "未知供应商"
        """
        name = Path(filename).stem
        # 去掉常见后缀
        name = re.sub(r"[_\-\s]*(报价单|报价表|报价|价格表|询价回复|回标)", "", name)
        # 去掉日期模式
        name = re.sub(r"\d{4}[-/]?\d{2}[-/]?\d{2}", "", name)
        # 清理
        name = name.strip(" _-")
        return name if name else "未知供应商"
```

**注意：** 本任务 API 路由全面使用 Task 1.6 定义的 Pydantic 模型作为请求体和 `response_model`。`TableToggleRequest` 需在 Task 1.6 的 `models/table.py` 中补充定义（见下方 API 代码）。

### api/files.py

```python
from fastapi import APIRouter, HTTPException, UploadFile, File, Path as PathParam
from services.file_service import FileService
from services.project_service import ProjectService
from models.file import (
    FileUploadResponse,
    SupplierConfirmRequest,
    SupplierFileResponse,
)
from models.table import RawTableResponse, TableToggleRequest, TableToggleResponse

router = APIRouter(tags=["文件导入"])
file_service = FileService()
project_service = ProjectService()


@router.post("/projects/{project_id}/files", response_model=FileUploadResponse)
async def upload_file(project_id: str, file: UploadFile = File(...)):
    """上传供应商文件，异步解析，返回 task_id 和 file_id"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    content = await file.read()
    try:
        result = file_service.import_file(project_id, file.filename or "unknown", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.get("/projects/{project_id}/files", response_model=list[SupplierFileResponse])
async def list_files(project_id: str):
    """获取项目的所有已导入文件"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return file_service.get_files(project_id)


@router.put("/files/{file_id}/confirm-supplier", response_model=SupplierFileResponse)
async def confirm_supplier(file_id: str, body: SupplierConfirmRequest):
    """确认供应商名称"""
    result = file_service.confirm_supplier(file_id, body.supplier_name, body.project_id)
    if not result:
        raise HTTPException(status_code=404, detail="文件不存在")
    return result


@router.get("/projects/{project_id}/tables", response_model=list[RawTableResponse])
async def list_tables(project_id: str):
    """获取项目的所有解析表格"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return file_service.get_tables(project_id)


@router.put("/tables/{table_id}/toggle-selection", response_model=TableToggleResponse)
async def toggle_table_selection(table_id: str, body: TableToggleRequest):
    """切换表格参与比价状态"""
    result = file_service.toggle_table_selection(table_id, body.project_id)
    if not result:
        raise HTTPException(status_code=404, detail="表格不存在")
    return result
```

### main.py 修改

添加 files 路由：

```python
from api.files import router as files_router
app.include_router(files_router, prefix="/api")
```

## 测试与验收

### tests/test_file_repo.py

```python
import pytest
from db.database import Database
from db.file_repo import FileRepo


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    return database


@pytest.fixture
def repo(db):
    return FileRepo(db)


def test_insert_and_get(repo):
    result = repo.insert("f1", "p1", "供应商A", "test.xlsx",
                         "source_files/f1.xlsx", "xlsx", "structure")
    assert result["id"] == "f1"
    assert result["supplier_name"] == "供应商A"
    assert result["supplier_confirmed"] == 0

    got = repo.get_by_id("f1")
    assert got is not None
    assert got["project_id"] == "p1"


def test_confirm_supplier(repo):
    repo.insert("f1", "p1", "猜测名", "test.xlsx",
                "source_files/f1.xlsx", "xlsx", "structure")
    result = repo.confirm_supplier("f1", "真实供应商")
    assert result["supplier_name"] == "真实供应商"
    assert result["supplier_confirmed"] == 1


def test_list_by_project(repo):
    repo.insert("f1", "p1", "A", "a.xlsx", "source_files/f1.xlsx", "xlsx", "structure")
    repo.insert("f2", "p1", "B", "b.xlsx", "source_files/f2.xlsx", "xlsx", "structure")
    repo.insert("f3", "p2", "C", "c.xlsx", "source_files/f3.xlsx", "xlsx", "structure")
    result = repo.list_by_project("p1")
    assert len(result) == 2
```

### tests/test_table_repo.py

```python
import pytest
from db.database import Database
from db.file_repo import FileRepo
from db.table_repo import TableRepo


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    return database


@pytest.fixture
def file_repo(db):
    return FileRepo(db)


@pytest.fixture
def table_repo(db):
    return TableRepo(db)


@pytest.fixture
def setup_file(file_repo):
    file_repo.insert("f1", "p1", "供应商A", "test.xlsx",
                     "source_files/f1.xlsx", "xlsx", "structure")


def test_insert_and_get(table_repo, setup_file):
    result = table_repo.insert("t1", "f1", 0, "Sheet1", None, 10, 3,
                               {"headers": ["A", "B", "C"], "rows": []})
    assert result["id"] == "t1"
    assert result["selected"] == 1


def test_toggle_selection(table_repo, setup_file):
    table_repo.insert("t1", "f1", 0, "Sheet1", None, 10, 3,
                      {"headers": [], "rows": []})
    result = table_repo.toggle_selection("t1")
    assert result["selected"] == 0
    result = table_repo.toggle_selection("t1")
    assert result["selected"] == 1


def test_list_by_file(table_repo, setup_file):
    table_repo.insert("t1", "f1", 0, "Sheet1", None, 5, 3,
                      {"headers": [], "rows": []})
    table_repo.insert("t2", "f1", 1, "Sheet2", None, 8, 4,
                      {"headers": [], "rows": []})
    result = table_repo.list_by_file("f1")
    assert len(result) == 2
    assert result[0]["table_index"] == 0
```

### tests/test_file_api.py

```python
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def _use_temp_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    from config import Settings
    import config
    config.settings = Settings()


@pytest.fixture
async def client():
    from main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_xlsx(tmp_path) -> Path:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报价"
    ws.append(["商品", "单价", "数量"])
    ws.append(["电脑", "5000", "10"])
    path = tmp_path / "联想_报价单.xlsx"
    wb.save(path)
    return path


@pytest.mark.anyio
async def test_upload_file(client, sample_xlsx):
    """上传文件 → 返回 file_id + task_id"""
    # 先创建项目
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    # 上传文件
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
async def test_upload_unsupported_type(client, tmp_path):
    """上传不支持的文件类型 → 400"""
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
async def test_upload_to_nonexistent_project(client, sample_xlsx):
    """上传到不存在的项目 → 404"""
    with open(sample_xlsx, "rb") as f:
        resp = await client.post(
            "/api/projects/nonexistent/files",
            files={"file": ("test.xlsx", f, "application/octet-stream")},
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_confirm_supplier(client, sample_xlsx):
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
async def test_list_tables_empty(client):
    """项目无文件时 → 空表格列表"""
    resp = await client.post("/api/projects", json={"name": "测试"})
    project_id = resp.json()["id"]

    resp = await client.get(f"/api/projects/{project_id}/tables")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_guess_supplier_name():
    """供应商名称猜测规则"""
    from services.file_service import FileService
    guess = FileService._guess_supplier_name
    assert guess("联想_报价单.xlsx") == "联想"
    assert guess("华为报价.docx") == "华为"
    assert guess("Dell_报价表_2024-01-15.pdf") == "Dell"
    assert guess("报价单.xlsx") == "未知供应商"
```

### 门禁检查

```bash
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest -x -q
```

**断言清单：**
- `POST /api/projects/{id}/files` → 200 + 返回 file_id, task_id, supplier_name_guess
- 不支持的文件类型 → 400
- 不存在的项目 → 404
- `PUT /api/files/{id}/confirm-supplier` → supplier_confirmed == true
- `GET /api/projects/{id}/tables` → 返回表格列表（空项目返回 []）
- `PUT /api/tables/{id}/toggle-selection` → selected 状态切换
- 供应商名称猜测：去掉报价单/日期后缀，空值返回 "未知供应商"
- FileRepo/TableRepo 的 CRUD 操作正确

## 提交

```bash
git add backend/db/file_repo.py backend/db/table_repo.py \
       backend/services/file_service.py backend/api/files.py \
       backend/main.py \
       backend/tests/test_file_repo.py backend/tests/test_table_repo.py \
       backend/tests/test_file_api.py
git commit -m "Phase 1.5: 文件导入 API — 上传/异步解析/供应商确认/表格选择"
```
