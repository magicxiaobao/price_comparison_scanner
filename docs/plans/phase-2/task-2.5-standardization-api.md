# Task 2.5: 标准化 API + 手工修正 API + 失效传播

## 输入条件

- Task 2.1 完成（`services/audit_log_service.py` 就绪）
- Task 2.4 完成（`engines/table_standardizer.py` 就绪）
- Task 2.6 完成（`models/standardization.py` 就绪）
- Phase 1 完成（TaskManager、raw_tables 数据就绪）

## 输出物

- 创建: `backend/api/standardization.py`
- 创建: `backend/db/standardized_row_repo.py`
- 修改: `backend/services/project_service.py`（新增 `run_standardization()`、`modify_standardized_row()`、`_propagate_dirty()`）
- 修改: `backend/main.py`（注册 standardization 路由）
- 创建: `backend/tests/test_standardization_api.py`

## 禁止修改

- 不修改 `db/schema.sql`（表已存在）
- 不修改 `engines/rule_engine.py`（已稳定）
- 不修改 `engines/table_standardizer.py`（已稳定）
- 不修改 `frontend/`

## 实现规格

### db/standardized_row_repo.py

```python
from db.database import Database

class StandardizedRowRepo:
    """标准化行数据访问层"""

    def __init__(self, db: Database):
        self.db = db

    def insert_batch(self, rows: list[dict]) -> int:
        """批量插入标准化行，返回插入行数"""
        ...

    def get_by_project(self, project_id: str) -> list[dict]:
        """按项目 ID 查询所有标准化行（通过 supplier_file_id JOIN）"""
        ...

    def get_by_id(self, row_id: str) -> dict | None:
        """按 ID 查询单行"""
        ...

    def update_field(self, row_id: str, field_name: str, new_value: str | float | None) -> dict | None:
        """更新单个字段值，同时设置 is_manually_modified=1，返回更新后的行"""
        ...

    def delete_by_raw_table(self, raw_table_id: str) -> int:
        """按 raw_table_id 删除标准化行（重新标准化前清理）"""
        ...

    def delete_by_project(self, project_id: str) -> int:
        """按项目删除所有标准化行"""
        ...
```

### services/project_service.py 新增方法

```python
class ProjectService:
    # ... 已有方法 ...

    def run_standardization(self, project_id: str, force: bool = False) -> str:
        """
        执行标准化（异步任务）。
        1. 获取项目所有已选择的 raw_tables
        2. 若 force=True 或无已有结果，清除旧数据
        3. 对每个 raw_table 调用 TableStandardizer.standardize()
        4. 取出 column_mapping_info，写入 raw_tables.column_mapping_info 字段（JSON）
        5. 通过 StandardizedRowRepo 批量写入 rows
        6. AuditLogService 记录操作（action_type='standardize', action_source='system'）
        7. 更新 normalize_status='completed'
        返回 task_id
        """
        ...

    def get_standardized_rows(self, project_id: str) -> list[dict]:
        """获取项目所有标准化行"""
        ...

    def modify_standardized_row(self, row_id: str, field: str, new_value: str | float | None) -> dict:
        """
        手工修正标准化行字段。
        1. 通过 repo 获取当前值
        2. 通过 repo 更新字段
        3. AuditLogService 记录（action_type='modify_field', action_source='user'）
        4. _propagate_dirty(project_id, from_stage='normalize')
        返回 FieldModifyResponse 数据
        """
        ...

    def _propagate_dirty(self, project_id: str, from_stage: str) -> list[str]:
        """
        失效传播。
        根据技术架构 4.3 定义的传播链：
        - from_stage='normalize' → grouping_status='dirty', compliance_status='dirty', comparison_status='dirty'
        - from_stage='grouping' → compliance_status='dirty', comparison_status='dirty'
        - from_stage='compliance' → comparison_status='dirty'
        返回被标记为 dirty 的阶段列表。
        通过 ProjectRepo 更新阶段状态。
        """
        stage_order = ['normalize', 'grouping', 'compliance', 'comparison']
        dirty_stages = []
        start_idx = stage_order.index(from_stage) + 1
        for stage in stage_order[start_idx:]:
            status_field = f"{stage}_status"
            # 通过 repo 更新对应状态为 'dirty'（跳过 'skipped' 的 compliance）
            ...
            dirty_stages.append(stage)
        return dirty_stages
```

**失效传播规则（技术架构 4.3）：**

```
触发: 修改 standardized_rows → grouping dirty → compliance dirty → comparison dirty
触发: 新增/删除 supplier_file → normalize dirty → grouping dirty → compliance dirty → comparison dirty
```

- 失效后下游数据**保留但标记为 stale**（不删除）
- `compliance_status='skipped'` 时不改为 `dirty`，保持 `skipped`

### api/standardization.py

```python
from fastapi import APIRouter, HTTPException
from models.standardization import (
    StandardizeRequest, StandardizeTaskResponse, StandardizedRowResponse,
    FieldModifyRequest, FieldModifyResponse,
)
from services.project_service import ProjectService

router = APIRouter(tags=["标准化"])
service = ProjectService()

@router.post("/projects/{project_id}/standardize", response_model=StandardizeTaskResponse)
async def run_standardization(project_id: str, req: StandardizeRequest | None = None):
    """
    执行标准化（异步）。
    返回 task_id。
    """
    force = req.force if req else False
    task_id = service.run_standardization(project_id, force=force)
    return StandardizeTaskResponse(task_id=task_id)

@router.get("/projects/{project_id}/standardized-rows", response_model=list[StandardizedRowResponse])
async def get_standardized_rows(project_id: str):
    """获取标准化结果"""
    rows = service.get_standardized_rows(project_id)
    return rows

@router.put("/standardized-rows/{row_id}", response_model=FieldModifyResponse)
async def modify_standardized_row(row_id: str, req: FieldModifyRequest):
    """
    手工修正字段值。
    触发 AuditLog 记录 + 失效传播。
    """
    result = service.modify_standardized_row(row_id, req.field, req.new_value)
    return result

@router.get("/projects/{project_id}/column-mapping-info")
async def get_column_mapping_info(project_id: str):
    """
    获取项目的列名映射信息（供 ColumnMappingPanel 使用）。
    返回每个 raw_table 的映射状态：confirmed / unmapped / conflict。
    """
    info = service.get_column_mapping_info(project_id)
    return info
```

### main.py 修改

```python
from api.standardization import router as standardization_router
app.include_router(standardization_router, prefix="/api")
```

**关键设计点：**

1. **service 层禁止直接执行 SQL**，必须通过 `StandardizedRowRepo` 和 `ProjectRepo`
2. **手工修正流程**：获取旧值 → 更新字段 → AuditLog 记录 → 失效传播 → 返回响应
3. **标准化为异步任务**：通过 TaskManager 提交，返回 task_id
4. **失效传播**：`_propagate_dirty()` 在每次修改操作后同步调用
5. **field 白名单校验**：手工修正的 `field` 必须在 9 个标准字段中
6. **JSON 字段序列化**：`source_location`、`column_mapping`、`hit_rule_snapshots` 通过 Pydantic model 序列化后存入 TEXT 字段

## 测试与验收

### fixture 设计

```python
@pytest.fixture
def project_with_raw_data(tmp_path, monkeypatch):
    """
    准备：
    1. 临时 APP_DATA_DIR
    2. 创建项目
    3. 插入 supplier_file + raw_table（模拟导入完成）
    4. 返回 (project_id, raw_table_id, supplier_file_id)
    所有数据在 tmp_path 中，不依赖外部文件。
    """
    ...
```

### 测试用例清单

```python
# ---- 标准化执行 ----
# test_standardize_basic — 执行标准化返回 task_id
# test_standardize_creates_rows — 标准化后可查到 standardized_rows
# test_standardize_force — force=True 时清除旧数据后重新标准化

# ---- 获取结果 ----
# test_get_standardized_rows — 返回正确的标准化行列表
# test_get_standardized_rows_empty — 未标准化时返回空列表

# ---- 手工修正 ----
# test_modify_field_success — 修正 unit_price 成功
# test_modify_field_audit_log — 修正后 audit_logs 有记录
# test_modify_field_propagate_dirty — 修正后下游阶段标记 dirty
# test_modify_field_invalid — 无效字段名返回 400/422
# test_modify_field_not_found — 不存在的 row_id 返回 404

# ---- 失效传播 ----
# test_propagate_dirty_from_normalize — normalize → grouping/compliance/comparison dirty
# test_propagate_dirty_skip_skipped — compliance=skipped 时保持 skipped

# ---- 异步任务集成 ----
# test_standardize_task_status — 可通过 task API 查询标准化进度
```

**断言清单：**

- `POST /api/projects/{id}/standardize` → 200，返回包含 `taskId` 的 JSON
- `GET /api/projects/{id}/standardized-rows` → 200，返回列表
- 标准化行包含所有 9 个标准字段 + `sourceLocation` + `hitRuleSnapshots`
- `PUT /api/standardized-rows/{id}` → 200，返回 `success=true` + `auditLog` + `dirtyStages`
- 手工修正后 `audit_logs` 表有对应记录（`action_type='modify_field'`）
- 手工修正后 `grouping_status='dirty'`、`comparison_status='dirty'`
- 无效字段名（不在标准字段白名单中）→ 400 或 422
- `compliance_status='skipped'` 时不被传播为 `dirty`

**门禁命令：**

```bash
cd backend
ruff check api/standardization.py db/standardized_row_repo.py tests/test_standardization_api.py
mypy api/standardization.py db/standardized_row_repo.py --ignore-missing-imports
pytest tests/test_standardization_api.py -x -q
```

## 提交

```bash
git add backend/api/standardization.py backend/db/standardized_row_repo.py \
       backend/services/project_service.py backend/main.py \
       backend/tests/test_standardization_api.py
git commit -m "Phase 2.5: 标准化 API + 手工修正 + 失效传播 + AuditLog 集成"
```
