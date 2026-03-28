# Task 4.5: 比价 API

## 输入条件

- Task 4.4 完成（PriceComparator + ComparisonRepo + ComparisonService 可用）
- Task 4.3 完成（ComplianceRepo 可用 — ComparisonService._get_eligible_supplier_ids() 依赖 ComplianceRepo）  <!-- [C7-fix] 补充实际依赖 -->
- TaskManager 异步框架可用（Phase 1 已建好）

## 输出物

- 创建: `backend/api/comparison.py`
- 修改: `backend/main.py`（注册 comparison 路由）
- 创建: `backend/tests/test_comparison_api.py`

## 禁止修改

- 不修改 `backend/engines/price_comparator.py`（已稳定）
- 不修改 `backend/db/comparison_repo.py`（已稳定）
- 不修改 `backend/services/comparison_service.py`（已稳定）
- 不修改 `backend/models/comparison.py`（已稳定）
- 不修改 `frontend/`

## 实现规格

### api/comparison.py

```python
from fastapi import APIRouter
from models.comparison import ComparisonGenerateResponse, ComparisonResultResponse
from services.comparison_service import ComparisonService
from api.deps import get_project_db

router = APIRouter(tags=["比价"])


def _get_service(project_id: str) -> ComparisonService:
    db = get_project_db(project_id)
    return ComparisonService(db)


@router.post("/projects/{project_id}/comparison/generate", response_model=ComparisonGenerateResponse)
async def generate_comparison(project_id: str):
    """生成比价结果（异步任务）"""
    from services.task_manager import task_manager
    task_id = task_manager.submit(
        task_type="comparison",
        params={"project_id": project_id},
        callback=lambda: _get_service(project_id).generate_comparison(project_id),
    )
    return ComparisonGenerateResponse(task_id=task_id)


@router.get("/projects/{project_id}/comparison", response_model=list[ComparisonResultResponse])
async def get_comparison(project_id: str):
    """获取比价结果"""
    service = _get_service(project_id)
    return service.list_results(project_id)
```

### main.py 修改

追加路由注册：

```python
from api.comparison import router as comparison_router
app.include_router(comparison_router, prefix="/api")
```

## 测试与验收

### tests/test_comparison_api.py

```python
import pytest


class TestComparisonAPI:
    @pytest.mark.anyio
    async def test_generate_returns_task_id(self, client_with_groups, project_id):
        resp = await client_with_groups.post(
            f"/api/projects/{project_id}/comparison/generate",
        )
        assert resp.status_code == 200
        assert "task_id" in resp.json()

    @pytest.mark.anyio
    async def test_get_comparison_results(self, client_with_comparison, project_id):
        resp = await client_with_comparison.get(
            f"/api/projects/{project_id}/comparison",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for r in data:
            assert r["comparison_status"] in ("comparable", "blocked", "partial")
            assert "min_price" in r
            assert "effective_min_price" in r
            assert "supplier_prices" in r
            assert isinstance(r["supplier_prices"], list)
            assert "anomaly_details" in r
            assert "group_name" in r

    @pytest.mark.anyio
    async def test_get_comparison_empty(self, client_with_groups, project_id):
        """未生成比价时返回空列表"""
        resp = await client_with_groups.get(
            f"/api/projects/{project_id}/comparison",
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_comparison_without_requirements(self, client_with_comparison_no_req, project_id):
        """无需求标准时 effective_min_price == min_price"""
        resp = await client_with_comparison_no_req.get(
            f"/api/projects/{project_id}/comparison",
        )
        data = resp.json()
        for r in data:
            assert r["effective_min_price"] == r["min_price"]

    @pytest.mark.anyio
    async def test_comparison_status_updated(self, client_with_comparison, project_id):
        """比价完成后 comparison_status 变为 completed"""
        resp = await client_with_comparison.get(f"/api/projects/{project_id}")
        assert resp.json()["stage_statuses"]["comparison_status"] == "completed"
```

### 门禁命令

```bash
cd backend
ruff check api/comparison.py
mypy api/comparison.py --ignore-missing-imports
pytest tests/test_comparison_api.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| POST generate → 返回 task_id | 200 |
| GET comparison → 列表含完整字段 | 200 |
| comparison_status in (comparable, blocked, partial) | 枚举值正确 |
| supplier_prices 是列表 | 结构正确 |
| 无需求时 effective_min == min | 等同 |
| 未生成时返回空 | [] |
| 完成后 stage_status == completed | 阶段更新 |

## 提交

```bash
git add backend/api/comparison.py backend/main.py \
       backend/tests/test_comparison_api.py
git commit -m "Phase 4.5: 比价 API — generate/get 路由 + 异步任务"
```

## Review Notes（审查发现的 Medium/Low 问题）

### 实现约束（开发时必须处理）

- **[M10] POST /generate 缺错误处理**：应对以下情况返回 HTTP 错误：项目不存在(404)、无归组数据(422, "请先完成商品归组")。
- **[M11] 异步任务轮询说明**：导出/比价等异步任务统一使用 Phase 1 的 `GET /api/tasks/{task_id}/status` 查询状态，无需在本 Task 新增端点。前端轮询间隔建议 2 秒，超时 300 秒。

### Reviewer 提醒

- **[Low] 并发 generate 请求**：多次调用 generate 会清除旧结果，无去重机制。MVP 可接受，前端通过 disabled 按钮防止重复点击。
