# Task 1.6: 文件导入相关 Pydantic 模型

## 输入条件

- Phase 0 全部完成
- `backend/models/` 目录已存在（含 `project.py`）

## 输出物

- 创建: `backend/models/file.py`
- 创建: `backend/models/table.py`
- 创建: `backend/models/task.py`

## 禁止修改

- 不修改 `backend/models/project.py`（已稳定）
- 不修改 `backend/db/`
- 不修改 `backend/api/`
- 不修改 `backend/services/`
- 不修改 `backend/engines/`
- 不修改 `frontend/`

## 实现规格

### models/file.py

```python
from pydantic import BaseModel, Field
from typing import Optional


class SupplierFileCreate(BaseModel):
    """文件上传后内部使用的创建模型（API 层不直接用，由 service 构造）"""
    project_id: str
    supplier_name: str
    original_filename: str
    file_path: str
    file_type: str = Field(..., pattern=r"^(xlsx|docx|pdf|image)$")
    recognition_mode: str = Field(default="structure", pattern=r"^(structure|ocr|manual)$")


class SupplierFileResponse(BaseModel):
    """API 返回的文件信息"""
    id: str
    project_id: str
    supplier_name: str
    supplier_confirmed: bool
    original_filename: str
    file_path: str
    file_type: str
    recognition_mode: Optional[str] = None
    imported_at: str


class SupplierConfirmRequest(BaseModel):
    """确认供应商名称请求"""
    supplier_name: str = Field(..., min_length=1, max_length=200)
    project_id: str


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    task_id: str
    supplier_name_guess: str
```

### models/table.py

```python
from pydantic import BaseModel
from typing import Optional, Any


class RawTableResponse(BaseModel):
    """API 返回的原始表格信息"""
    id: str
    supplier_file_id: str
    table_index: int
    sheet_name: Optional[str] = None
    page_number: Optional[int] = None
    row_count: int
    column_count: int
    raw_data: Any                      # JSON 对象: {"headers": [...], "rows": [[...]]}
    selected: bool
    # 关联信息（来自 JOIN）
    supplier_name: Optional[str] = None
    original_filename: Optional[str] = None
    supplier_confirmed: Optional[bool] = None


class TableToggleResponse(BaseModel):
    """表格选择切换响应"""
    table_id: str
    selected: bool
```

### models/task.py

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class TaskStatusEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    task_id: str
    task_type: str
    status: TaskStatusEnum
    progress: float                    # 0.0 - 1.0
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
```

**设计要点：**
- `SupplierFileResponse.supplier_confirmed` 为 bool 类型（数据库中存储为 0/1 整数，API 层转换）
- `RawTableResponse.raw_data` 为 Any 类型，实际为 JSON 对象
- `RawTableResponse` 包含关联字段（supplier_name 等），来自 JOIN 查询
- `TaskStatusEnum` 与 `engines/task_manager.py` 中的 `TaskStatus` 枚举值一致
- 所有响应模型使用 Pydantic v2 风格

## 测试与验收

Pydantic 模型无需独立测试文件，其正确性由 API 测试（Task 1.5 的 test_file_api.py）间接验证。

### 门禁检查

```bash
cd backend
ruff check models/file.py models/table.py models/task.py
mypy models/file.py models/table.py models/task.py --ignore-missing-imports
```

**断言清单：**
- `ruff check` → 零警告
- `mypy` → 零错误
- `SupplierFileCreate(file_type="txt")` → ValidationError（pattern 约束）
- `SupplierConfirmRequest(supplier_name="", project_id="p1")` → ValidationError（min_length 约束）
- `TaskStatusEnum.QUEUED.value` == "queued"

## 提交

```bash
git add backend/models/file.py backend/models/table.py backend/models/task.py
git commit -m "Phase 1.6: 文件导入 Pydantic 模型 — SupplierFile/RawTable/TaskStatus"
```
