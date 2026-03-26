# Task 2.1: AuditLogService 操作留痕

## 输入条件

- Phase 1 完成（项目 CRUD、文件导入、数据库层就绪）
- `db/schema.sql` 中 `audit_logs` 表已建好（Phase 0 建表）

## 输出物

- 创建: `backend/services/audit_log_service.py`
- 创建: `backend/db/audit_log_repo.py`
- 创建: `backend/tests/test_audit_log.py`

## 禁止修改

- 不修改 `db/schema.sql`（表已存在）
- 不修改 `db/database.py`
- 不修改 `api/middleware.py`
- 不修改 `frontend/`

## 实现规格

### db/audit_log_repo.py

```python
from db.database import Database

class AuditLogRepo:
    """审计日志数据访问层 — 纯 SQL 操作"""

    def __init__(self, db: Database):
        self.db = db

    def insert(
        self,
        log_id: str,
        project_id: str,
        action_type: str,
        action_source: str,
        target_table: str | None,
        target_id: str | None,
        field_name: str | None,
        before_value: str | None,
        after_value: str | None,
        created_at: str,
    ) -> dict:
        """插入一条审计日志"""
        ...

    def list_by_project(self, project_id: str, limit: int = 100) -> list[dict]:
        """按项目 ID 查询审计日志，按时间降序"""
        ...

    def list_by_target(self, target_id: str) -> list[dict]:
        """按目标记录 ID 查询审计日志"""
        ...
```

### services/audit_log_service.py

```python
import uuid
from datetime import datetime, timezone
from db.database import Database
from db.audit_log_repo import AuditLogRepo

class AuditLogService:
    """操作留痕服务 — 记录所有修改操作到 audit_logs 表"""

    def __init__(self, db: Database):
        self.repo = AuditLogRepo(db)

    def log(
        self,
        project_id: str,
        action_type: str,           # import / standardize / group_confirm / group_split / modify_field / export
        action_source: str = "user", # user / system / import
        target_table: str | None = None,
        target_id: str | None = None,
        field_name: str | None = None,
        before_value: str | None = None,
        after_value: str | None = None,
    ) -> str:
        """记录一条操作日志，返回 log_id"""
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.repo.insert(
            log_id=log_id,
            project_id=project_id,
            action_type=action_type,
            action_source=action_source,
            target_table=target_table,
            target_id=target_id,
            field_name=field_name,
            before_value=before_value,
            after_value=after_value,
            created_at=now,
        )
        return log_id

    def get_project_logs(self, project_id: str, limit: int = 100) -> list[dict]:
        """获取项目的操作日志"""
        return self.repo.list_by_project(project_id, limit)

    def get_target_logs(self, target_id: str) -> list[dict]:
        """获取某个目标记录的操作日志"""
        return self.repo.list_by_target(target_id)
```

**关键设计点：**

- `AuditLogService` 不直接执行 SQL，通过 `AuditLogRepo` 操作
- `action_type` 取值范围：`import` / `standardize` / `group_confirm` / `group_split` / `modify_field` / `export`
- `action_source` 区分人工操作（`user`）、系统自动重算（`system`）、导入操作（`import`）
- `before_value` / `after_value` 统一转为字符串存储（数值型也转 str）
- 本 Task 仅实现 Service + Repo，不实现 API 端点（API 在后续 Task 中按需调用）

## 测试与验收

### tests/test_audit_log.py

```python
import pytest
from db.database import Database
from services.audit_log_service import AuditLogService

@pytest.fixture
def audit_service(tmp_path):
    """使用临时数据库的 AuditLogService"""
    db = Database(tmp_path / "test.db")
    # 初始化 schema（audit_logs 表）
    ...
    return AuditLogService(db)

# 测试用例清单：
# 1. test_log_modify_field — 记录字段修正，验证所有字段正确写入
# 2. test_log_standardize — 记录标准化操作
# 3. test_log_import — 记录导入操作，action_source='import'
# 4. test_get_project_logs — 按项目查询，验证降序排列
# 5. test_get_target_logs — 按目标 ID 查询
# 6. test_before_after_value_as_string — 数值类型转为字符串存储
# 7. test_log_returns_log_id — 返回值是有效 UUID
```

**断言清单：**

- `log()` 返回非空字符串（UUID 格式）
- 写入后通过 `get_project_logs()` 可查到对应记录
- `action_type` / `action_source` / `field_name` / `before_value` / `after_value` 字段值与写入一致
- `created_at` 为有效 ISO 8601 时间戳
- 多条日志按 `created_at` 降序排列
- 数值型 `before_value`/`after_value` 存储为字符串

**门禁命令：**

```bash
cd backend
ruff check services/audit_log_service.py db/audit_log_repo.py tests/test_audit_log.py
mypy services/audit_log_service.py db/audit_log_repo.py --ignore-missing-imports
pytest tests/test_audit_log.py -x -q
```

## 提交

```bash
git add backend/services/audit_log_service.py backend/db/audit_log_repo.py backend/tests/test_audit_log.py
git commit -m "Phase 2.1: AuditLogService 操作留痕 — 审计日志写入 + 项目/目标查询"
```
