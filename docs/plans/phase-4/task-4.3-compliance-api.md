# Task 4.3: 符合性 API（匹配 + 矩阵 + 确认 + 可接受标记）

## 输入条件

- Task 4.2 完成（ComplianceEvaluator 匹配逻辑 + ComplianceRepo + ComplianceService 完整可用）
- TaskManager 异步框架可用（Phase 1 已建好）

## 输出物

- 创建: `backend/api/compliance.py`
- 修改: `backend/main.py`（注册 compliance 路由）
- 创建: `backend/tests/test_compliance_api.py`

## 禁止修改

- 不修改 `backend/engines/compliance_evaluator.py`（已稳定）
- 不修改 `backend/db/compliance_repo.py`（已稳定）
- 不修改 `backend/services/compliance_service.py`（已稳定）
- 不修改 `backend/models/compliance.py`（已稳定）
- 不修改 `frontend/`

## 实现规格

### api/compliance.py

```python
from fastapi import APIRouter, HTTPException
from models.compliance import (
    ComplianceEvaluateResponse,
    ComplianceMatrixResponse,
    ComplianceConfirmRequest,
    ComplianceAcceptRequest,
    ComplianceMatchResponse,
)
from services.compliance_service import ComplianceService
from api.deps import get_project_db

router = APIRouter(tags=["符合性审查"])


def _get_service(project_id: str) -> ComplianceService:
    db = get_project_db(project_id)
    return ComplianceService(db)


@router.post("/projects/{project_id}/compliance/evaluate", response_model=ComplianceEvaluateResponse)
async def evaluate_compliance(project_id: str):
    """执行符合性匹配（异步任务）"""
    from services.task_manager import task_manager
    task_id = task_manager.submit(
        task_type="compliance_evaluate",
        params={"project_id": project_id},
        callback=lambda: _get_service(project_id).evaluate(project_id),
    )
    return ComplianceEvaluateResponse(task_id=task_id)


@router.get("/projects/{project_id}/compliance/matrix", response_model=ComplianceMatrixResponse)
async def get_compliance_matrix(project_id: str):
    """获取符合性矩阵"""
    service = _get_service(project_id)
    return service.get_matrix(project_id)


@router.put("/compliance/{match_id}/confirm")
async def confirm_match(match_id: str, req: ComplianceConfirmRequest):
    """确认匹配结果"""
    service = _find_service_for_match(match_id)
    if not service:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    result = service.confirm_match(match_id, req.status)
    return result


@router.put("/compliance/{match_id}/accept")
async def accept_match(match_id: str, req: ComplianceAcceptRequest):
    """标记部分符合为可接受"""
    service = _find_service_for_match(match_id)
    if not service:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    result = service.accept_match(match_id, req.is_acceptable)
    return result


def _find_service_for_match(match_id: str) -> ComplianceService | None:
    """根据 match_id 查找对应的 ComplianceService"""
    import json
    from pathlib import Path
    from api.deps import get_app_data_dir
    from db.database import Database
    from db.compliance_repo import ComplianceRepo

    config_path = get_app_data_dir() / "config.json"
    if not config_path.exists():
        return None
    config = json.loads(config_path.read_text(encoding="utf-8"))

    for p in config.get("recent_projects", []):
        db_path = Path(p["path"]) / "project.db"
        if not db_path.exists():
            continue
        db = Database(db_path)
        repo = ComplianceRepo(db)
        row = repo.get_by_id(match_id)
        if row:
            return ComplianceService(db)
    return None
```

### main.py 修改

追加路由注册：

```python
from api.compliance import router as compliance_router
app.include_router(compliance_router, prefix="/api")
```

## 测试与验收

### tests/test_compliance_api.py

```python
import pytest


class TestComplianceAPI:
    @pytest.mark.anyio
    async def test_evaluate_returns_task_id(self, client_with_requirements_and_groups, project_id):
        resp = await client_with_requirements_and_groups.post(
            f"/api/projects/{project_id}/compliance/evaluate",
        )
        assert resp.status_code == 200
        assert "task_id" in resp.json()

    @pytest.mark.anyio
    async def test_get_matrix(self, client_with_compliance_results, project_id):
        resp = await client_with_compliance_results.get(
            f"/api/projects/{project_id}/compliance/matrix",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "supplier_names" in data
        assert "rows" in data
        assert isinstance(data["rows"], list)
        for row in data["rows"]:
            assert "requirement" in row
            assert "suppliers" in row

    @pytest.mark.anyio
    async def test_confirm_match(self, client_with_compliance_results, first_match_id):
        resp = await client_with_compliance_results.put(
            f"/api/compliance/{first_match_id}/confirm",
            json={"status": "match"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "match"
        assert data["needs_review"] == 0

    @pytest.mark.anyio
    async def test_accept_match(self, client_with_compliance_results, partial_match_id):
        resp = await client_with_compliance_results.put(
            f"/api/compliance/{partial_match_id}/accept",
            json={"is_acceptable": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_acceptable"] == 1

    @pytest.mark.anyio
    async def test_confirm_nonexistent_match(self, client_with_compliance_results):
        resp = await client_with_compliance_results.put(
            "/api/compliance/nonexistent/confirm",
            json={"status": "match"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_dirty_propagation_after_confirm(
        self, client_with_compliance_results, project_id, first_match_id
    ):
        """确认匹配结果后 comparison_status 变为 dirty"""
        await client_with_compliance_results.put(
            f"/api/compliance/{first_match_id}/confirm",
            json={"status": "match"},
        )
        resp = await client_with_compliance_results.get(f"/api/projects/{project_id}")
        assert resp.json()["stage_statuses"]["comparison_status"] == "dirty"

    @pytest.mark.anyio
    async def test_invalid_confirm_status(self, client_with_compliance_results, first_match_id):
        resp = await client_with_compliance_results.put(
            f"/api/compliance/{first_match_id}/confirm",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422
```

### 门禁命令

```bash
cd backend
ruff check api/compliance.py
mypy api/compliance.py --ignore-missing-imports
pytest tests/test_compliance_api.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| POST evaluate → 返回 task_id | 200 |
| GET matrix → supplier_names + rows | 200 |
| 矩阵行包含 requirement + suppliers | 结构正确 |
| PUT confirm → status 更新 + needs_review=0 | 200 |
| PUT accept → is_acceptable 更新 | 200 |
| 确认后 → comparison_status == dirty | 失效传播生效 |
| 不存在 match_id → 404 | 404 |
| 无效 status → 422 | 422 |

## 提交

```bash
git add backend/api/compliance.py backend/main.py \
       backend/tests/test_compliance_api.py
git commit -m "Phase 4.3: 符合性 API — evaluate/matrix/confirm/accept 路由 + 异步任务 + 失效传播"
```
