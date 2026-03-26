# Task 0.4: 项目 CRUD API（最小版）

## 输入条件

- Task 0.2 完成（认证中间件就绪）
- Task 0.3 完成（数据库层 + schema 就绪）

## 输出物

- 创建: `backend/models/project.py`
- 创建: `backend/api/deps.py`
- 修改: `backend/db/project_repo.py`（填充 CRUD 实现）
- 创建: `backend/services/project_service.py`
- 创建: `backend/api/projects.py`
- 修改: `backend/main.py`（注册 projects 路由）
- 创建: `backend/tests/test_projects.py`

## 禁止修改

- 不修改 `db/database.py`（已稳定）
- 不修改 `db/schema.sql`（已稳定）
- 不修改 `api/middleware.py`（已稳定）
- 不修改 `frontend/`

## 实现规格

**分层职责约束：**
- `ProjectRepo`：纯数据访问层，只做 SQL 操作，不生成 ID、不管目录、不操作全局配置
- `ProjectService`：业务编排层，负责 ID 生成、目录创建、调用 repo 写库、更新全局配置
- `api/projects.py`：路由层，仅做请求解析和响应组装，调用 service

**service 层禁止直接执行 SQL 语句**，必须通过 repo 方法操作数据库。

### models/project.py

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class StageStatuses(BaseModel):
    import_status: str = "pending"       # pending | completed | dirty
    normalize_status: str = "pending"
    grouping_status: str = "pending"
    compliance_status: str = "skipped"   # skipped | pending | completed | dirty
    comparison_status: str = "pending"

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)

class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    supplier_count: int = 0
    current_stage: str = "导入文件"

class ProjectDetail(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    stage_statuses: StageStatuses
```

**设计要点：**
- `ProjectCreate` 仅包含 `name`，ID 由服务端生成（UUID）
- `ProjectSummary` 用于列表展示（含供应商数和当前阶段简述）
- `ProjectDetail` 用于详情页（含完整阶段状态）
- Phase 0 只定义这些模型，其余 Pydantic 模型在后续 Phase 按需添加

### api/deps.py

```python
from pathlib import Path
from db.database import Database
from config import settings

def get_app_data_dir() -> Path:
    """获取应用数据目录，不存在则创建"""
    path = Path(settings.APP_DATA_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_global_config_path() -> Path:
    return get_app_data_dir() / "config.json"

def get_project_db(project_id: str) -> Database:
    """获取项目数据库实例"""
    project_dir = get_app_data_dir() / "projects" / project_id
    return Database(project_dir / "project.db")
```

### db/project_repo.py

```python
from datetime import datetime, timezone
from db.database import Database
from typing import Optional

class ProjectRepo:
    """项目表 CRUD — 纯数据访问层，不负责生成 ID 或管理目录"""

    def __init__(self, db: Database):
        self.db = db

    def insert(self, project_id: str, name: str) -> dict:
        """插入项目记录，返回项目 dict。ID 由调用方（service）提供。"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (project_id, name, now, now),
            )
        return self.get_by_id(project_id)

    def get_by_id(self, project_id: str) -> Optional[dict]:
        """按 ID 查询项目，返回 dict 或 None"""
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_all(self) -> list[dict]:
        """查询所有项目，按更新时间降序"""
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete(self, project_id: str) -> bool:
        """删除项目记录，返回是否有实际删除"""
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0
```

### services/project_service.py

```python
import json
import shutil
from pathlib import Path
from db.database import Database
from db.project_repo import ProjectRepo
from models.project import ProjectCreate, ProjectSummary, ProjectDetail, StageStatuses
from api.deps import get_app_data_dir

class ProjectService:
    """
    项目业务服务 — 协调目录管理、数据库操作、全局配置。
    职责边界：service 负责 ID 生成、目录创建、全局配置更新；repo 负责纯 SQL 操作。
    """

    def create_project(self, req: ProjectCreate) -> ProjectDetail:
        """新建项目：生成 ID → 创建目录 → 初始化数据库 → 通过 repo 写入记录 → 更新全局配置"""
        import uuid
        app_data = get_app_data_dir()
        project_id = str(uuid.uuid4())
        project_dir = app_data / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "source_files").mkdir(exist_ok=True)
        (project_dir / "exports").mkdir(exist_ok=True)

        db = Database(project_dir / "project.db")
        repo = ProjectRepo(db)
        repo.insert(project_id, req.name)

        # 更新全局最近项目列表
        self._update_recent_projects(project_id, req.name, project_dir)

        return self._to_detail(repo.get_by_id(project_id))

    def list_projects(self) -> list[ProjectSummary]:
        """从全局配置读取最近项目列表"""
        config = self._read_global_config()
        result = []
        for p in config.get("recent_projects", []):
            project_dir = Path(p["path"])
            if not (project_dir / "project.db").exists():
                continue
            db = Database(project_dir / "project.db")
            repo = ProjectRepo(db)
            row = repo.get_by_id(p["id"])
            if row:
                result.append(self._to_summary(row))
        return result

    def get_project(self, project_id: str) -> ProjectDetail | None:
        """获取项目详情"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            return None
        db = Database(project_dir / "project.db")
        repo = ProjectRepo(db)
        row = repo.get_by_id(project_id)
        return self._to_detail(row) if row else None

    def delete_project(self, project_id: str) -> bool:
        """删除项目：删除目录 + 从全局配置移除"""
        project_dir = self._find_project_dir(project_id)
        if not project_dir:
            return False
        if project_dir.exists():
            shutil.rmtree(project_dir)
        self._remove_from_recent(project_id)
        return True

    # ---- 私有方法 ----

    def _find_project_dir(self, project_id: str) -> Path | None:
        config = self._read_global_config()
        for p in config.get("recent_projects", []):
            if p["id"] == project_id:
                return Path(p["path"])
        return None

    def _read_global_config(self) -> dict:
        config_path = get_app_data_dir() / "config.json"
        if not config_path.exists():
            return {"recent_projects": []}
        return json.loads(config_path.read_text(encoding="utf-8"))

    def _write_global_config(self, config: dict) -> None:
        """原子写入：临时文件 → fsync → rename"""
        config_path = get_app_data_dir() / "config.json"
        tmp_path = config_path.with_suffix(".tmp")
        data = json.dumps(config, ensure_ascii=False, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            import os
            os.fsync(f.fileno())
        tmp_path.replace(config_path)

    def _update_recent_projects(self, project_id: str, name: str, project_dir: Path) -> None:
        config = self._read_global_config()
        recent = config.get("recent_projects", [])
        # 去重
        recent = [p for p in recent if p["id"] != project_id]
        # 新项目插入头部
        recent.insert(0, {"id": project_id, "name": name, "path": str(project_dir)})
        config["recent_projects"] = recent
        self._write_global_config(config)

    def _remove_from_recent(self, project_id: str) -> None:
        config = self._read_global_config()
        config["recent_projects"] = [p for p in config.get("recent_projects", []) if p["id"] != project_id]
        self._write_global_config(config)

    def _to_summary(self, row: dict) -> ProjectSummary:
        return ProjectSummary(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _to_detail(self, row: dict) -> ProjectDetail:
        return ProjectDetail(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            stage_statuses=StageStatuses(
                import_status=row.get("import_status", "pending"),
                normalize_status=row.get("normalize_status", "pending"),
                grouping_status=row.get("grouping_status", "pending"),
                compliance_status=row.get("compliance_status", "skipped"),
                comparison_status=row.get("comparison_status", "pending"),
            ),
        )
```

### api/projects.py

```python
from fastapi import APIRouter, HTTPException
from models.project import ProjectCreate, ProjectSummary, ProjectDetail
from services.project_service import ProjectService

router = APIRouter(tags=["项目管理"])
service = ProjectService()

@router.post("/projects", response_model=ProjectDetail)
async def create_project(req: ProjectCreate):
    return service.create_project(req)

@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects():
    return service.list_projects()

@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str):
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    deleted = service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"detail": "已删除"}
```

### main.py 修改

添加 projects 路由：

```python
from api.projects import router as projects_router
app.include_router(projects_router, prefix="/api")
```

### tests/test_projects.py

```python
import os
import tempfile
import pytest

@pytest.fixture(autouse=True)
def _use_temp_app_data(monkeypatch, tmp_path):
    """使用临时目录作为应用数据目录"""
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

@pytest.mark.anyio
async def test_create_project(client):
    resp = await client.post("/api/projects", json={"name": "测试项目A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试项目A"
    assert "id" in data
    assert "stage_statuses" in data
    assert data["stage_statuses"]["import_status"] == "pending"
    assert data["stage_statuses"]["compliance_status"] == "skipped"

@pytest.mark.anyio
async def test_create_project_empty_name(client):
    resp = await client.post("/api/projects", json={"name": ""})
    assert resp.status_code == 422

@pytest.mark.anyio
async def test_list_projects_empty(client):
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.anyio
async def test_list_projects_after_create(client):
    await client.post("/api/projects", json={"name": "项目1"})
    await client.post("/api/projects", json={"name": "项目2"})
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 最新的在前面
    assert data[0]["name"] == "项目2"

@pytest.mark.anyio
async def test_get_project(client):
    create_resp = await client.post("/api/projects", json={"name": "详情项目"})
    project_id = create_resp.json()["id"]
    resp = await client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "详情项目"
    assert data["id"] == project_id

@pytest.mark.anyio
async def test_get_project_not_found(client):
    resp = await client.get("/api/projects/nonexistent-id")
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_delete_project(client):
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
async def test_delete_project_not_found(client):
    resp = await client.delete("/api/projects/nonexistent-id")
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_project_creates_directory_structure(client, tmp_path):
    create_resp = await client.post("/api/projects", json={"name": "目录检查"})
    project_id = create_resp.json()["id"]
    project_dir = tmp_path / "projects" / project_id
    assert project_dir.exists()
    assert (project_dir / "project.db").exists()
    assert (project_dir / "source_files").is_dir()
    assert (project_dir / "exports").is_dir()
```

## 测试与验收

```bash
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest -x -q                          # 预期全部通过（health 2 + middleware 6 + database 8 + projects 9 = 25）
```

**断言清单：**
- 创建项目 → 返回 200 + 包含 id, name, stage_statuses
- 空名称 → 422
- 列表查询 → 按更新时间降序
- 详情查询 → 包含完整阶段状态
- 不存在的项目 → 404
- 删除项目 → 目录和数据库记录都清除
- 项目目录结构正确（project.db + source_files/ + exports/）
- 全局 config.json 原子写入

## 提交

```bash
git add backend/models/ backend/api/deps.py backend/api/projects.py \
       backend/db/project_repo.py backend/services/project_service.py \
       backend/main.py backend/tests/test_projects.py
git commit -m "Phase 0.4: 项目 CRUD API — 创建/列表/详情/删除 + 全局配置管理"
```
