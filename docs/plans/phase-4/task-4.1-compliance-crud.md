# Task 4.1: ComplianceEvaluator — 需求标准 CRUD + 导入导出

## 输入条件

- Phase 3 完成（归组相关模块可用）
- Task 4.11 完成（compliance Pydantic 模型已定义）
- 数据库 `requirement_items` 表结构已就绪（Phase 0 建表）

## 输出物

- 创建: `backend/db/requirement_repo.py`
- 创建: `backend/engines/compliance_evaluator.py`（本 Task 仅实现 CRUD + 导入导出部分，匹配逻辑在 Task 4.2）
- 创建: `backend/api/requirements.py`
- 创建: `backend/services/compliance_service.py`（本 Task 仅实现需求 CRUD 部分）
- 修改: `backend/main.py`（注册 requirements 路由）
- 创建: `backend/tests/test_requirement_repo.py`
- 创建: `backend/tests/test_requirements_api.py`

## 禁止修改

- 不修改 `backend/db/schema.sql`
- 不修改 `backend/models/compliance.py`（已稳定）
- 不修改已有的其他 API 路由文件
- 不修改 `frontend/`

## 实现规格

**分层职责约束：**
- `RequirementRepo`：纯数据访问层，只做 SQL 操作
- `ComplianceEvaluator`：引擎层，不依赖 FastAPI/DB，本 Task 实现导入解析逻辑
- `ComplianceService`：业务编排层，协调 engine + repo + 失效传播
- `api/requirements.py`：路由层，仅做请求解析和响应组装

**service 层禁止直接执行 SQL 语句**，必须通过 repo 方法操作数据库。

### db/requirement_repo.py

```python
from db.database import Database
from typing import Optional
from datetime import datetime, timezone


class RequirementRepo:
    """requirement_items 表操作 — 纯数据访问层"""

    def __init__(self, db: Database):
        self.db = db

    def insert(
        self,
        req_id: str,
        project_id: str,
        code: Optional[str],
        category: str,
        title: str,
        description: Optional[str],
        is_mandatory: bool,
        match_type: str,
        expected_value: Optional[str],
        operator: Optional[str],
        sort_order: int,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO requirement_items
                   (id, project_id, code, category, title, description,
                    is_mandatory, match_type, expected_value, operator, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (req_id, project_id, code, category, title, description,
                 1 if is_mandatory else 0, match_type, expected_value, operator, sort_order, now),
            )
        return self.get_by_id(req_id)

    def get_by_id(self, req_id: str) -> Optional[dict]:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM requirement_items WHERE id = ?", (req_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM requirement_items WHERE project_id = ? ORDER BY sort_order, created_at",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update(self, req_id: str, updates: dict) -> Optional[dict]:
        """部分更新需求项，updates 为字段名→值的 dict"""
        if not updates:
            return self.get_by_id(req_id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [req_id]
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE requirement_items SET {set_clause} WHERE id = ?",
                values,
            )
        return self.get_by_id(req_id)

    def delete(self, req_id: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM requirement_items WHERE id = ?", (req_id,))
            return cursor.rowcount > 0

    def count_by_project(self, project_id: str) -> int:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return cursor.fetchone()[0]

    def get_max_sort_order(self, project_id: str) -> int:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return cursor.fetchone()[0]

    def delete_all_by_project(self, project_id: str) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount
```

### engines/compliance_evaluator.py（本 Task 部分）

```python
from typing import Optional
from dataclasses import dataclass


@dataclass
class ParsedRequirement:
    """从 Excel 模板解析出的需求项"""
    code: Optional[str]
    category: str
    title: str
    description: Optional[str]
    is_mandatory: bool
    match_type: str
    expected_value: Optional[str]
    operator: Optional[str]


class ComplianceEvaluator:
    """需求标准管理 + 供应商符合性匹配引擎（可选模块）"""

    # ---- 导入解析 ----

    def parse_requirements_excel(self, file_path: str) -> list[ParsedRequirement]:
        """
        从模板 Excel 导入需求标准。

        模板格式：
        | 需求编号 | 需求分类 | 需求标题 | 需求描述 | 是否必选 | 判断类型 | 目标值 | 比较操作符 |

        注意：首次使用 openpyxl 读取 API 时，必须用 Context7 查文档。
        """
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True)
        ws = wb.active
        results: list[ParsedRequirement] = []

        header_row = 1
        for row_idx, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=2):
            if not row or not row[2]:  # title 列为空则跳过
                continue
            code = str(row[0]).strip() if row[0] else None
            category = str(row[1]).strip() if row[1] else "功能要求"
            title = str(row[2]).strip()
            description = str(row[3]).strip() if row[3] else None
            is_mandatory = str(row[4]).strip() in ("是", "必选", "1", "true", "True") if row[4] else True
            match_type = str(row[5]).strip().lower() if row[5] else "manual"
            if match_type not in ("keyword", "numeric", "manual"):
                match_type = "manual"
            expected_value = str(row[6]).strip() if row[6] else None
            operator = str(row[7]).strip().lower() if len(row) > 7 and row[7] else None
            if operator and operator not in ("gte", "lte", "eq", "range"):
                operator = None

            results.append(ParsedRequirement(
                code=code,
                category=category if category in ("功能要求", "技术规格", "商务条款", "服务要求", "交付要求") else "功能要求",
                title=title,
                description=description,
                is_mandatory=is_mandatory,
                match_type=match_type,
                expected_value=expected_value,
                operator=operator,
            ))

        wb.close()
        return results

    def export_requirements_template(self, requirements: list[dict], output_path: str) -> str:
        """
        导出需求标准为 Excel 模板。

        注意：首次使用 openpyxl 写入 + 样式 API 时，必须用 Context7 查文档。
        """
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "需求标准"

        headers = ["需求编号", "需求分类", "需求标题", "需求描述", "是否必选", "判断类型", "目标值", "比较操作符"]
        ws.append(headers)

        for req in requirements:
            ws.append([
                req.get("code", ""),
                req.get("category", ""),
                req.get("title", ""),
                req.get("description", ""),
                "是" if req.get("is_mandatory", True) else "否",
                req.get("match_type", ""),
                req.get("expected_value", ""),
                req.get("operator", ""),
            ])

        wb.save(output_path)
        return output_path

    # ---- 匹配逻辑在 Task 4.2 中实现 ----
```

### services/compliance_service.py（本 Task 部分）

```python
import uuid
from datetime import datetime, timezone
from db.database import Database
from db.requirement_repo import RequirementRepo
from engines.compliance_evaluator import ComplianceEvaluator
from models.compliance import (
    RequirementCreate, RequirementUpdate, RequirementResponse,
    RequirementImportResult,
)


class ComplianceService:
    """符合性业务编排 — 协调 ComplianceEvaluator + RequirementRepo + 失效传播"""

    def __init__(self, db: Database):
        self.db = db
        self.repo = RequirementRepo(db)
        self.engine = ComplianceEvaluator()

    # ---- 需求标准 CRUD ----

    def create_requirement(self, project_id: str, req: RequirementCreate) -> RequirementResponse:
        req_id = str(uuid.uuid4())
        sort_order = self.repo.get_max_sort_order(project_id) + 1
        code = req.code or self._generate_code(project_id)

        row = self.repo.insert(
            req_id=req_id,
            project_id=project_id,
            code=code,
            category=req.category,
            title=req.title,
            description=req.description,
            is_mandatory=req.is_mandatory,
            match_type=req.match_type,
            expected_value=req.expected_value,
            operator=req.operator,
            sort_order=sort_order,
        )

        # 首次新增需求项 → compliance_status 从 skipped 切换为 pending
        self._activate_compliance_stage(project_id)
        # 失效传播：需求变更 → compliance dirty → comparison dirty
        self._propagate_dirty(project_id)

        return self._to_response(row)

    def list_requirements(self, project_id: str) -> list[RequirementResponse]:
        rows = self.repo.list_by_project(project_id)
        return [self._to_response(r) for r in rows]

    def update_requirement(self, req_id: str, req: RequirementUpdate) -> RequirementResponse:
        updates = req.model_dump(exclude_unset=True)
        if "is_mandatory" in updates:
            updates["is_mandatory"] = 1 if updates["is_mandatory"] else 0
        row = self.repo.update(req_id, updates)
        if not row:
            raise ValueError(f"需求项不存在: {req_id}")

        self._propagate_dirty(row["project_id"])
        return self._to_response(row)

    def delete_requirement(self, req_id: str) -> bool:
        row = self.repo.get_by_id(req_id)
        if not row:
            return False
        project_id = row["project_id"]
        self.repo.delete(req_id)

        # 检查是否还有需求项，若无则恢复 skipped
        if self.repo.count_by_project(project_id) == 0:
            self._deactivate_compliance_stage(project_id)
        else:
            self._propagate_dirty(project_id)

        return True

    # ---- 导入导出 ----

    def import_requirements(self, project_id: str, file_path: str) -> RequirementImportResult:
        parsed = self.engine.parse_requirements_excel(file_path)
        imported = 0
        skipped = 0
        errors: list[str] = []

        for item in parsed:
            try:
                req_id = str(uuid.uuid4())
                sort_order = self.repo.get_max_sort_order(project_id) + 1
                code = item.code or self._generate_code(project_id)
                self.repo.insert(
                    req_id=req_id,
                    project_id=project_id,
                    code=code,
                    category=item.category,
                    title=item.title,
                    description=item.description,
                    is_mandatory=item.is_mandatory,
                    match_type=item.match_type,
                    expected_value=item.expected_value,
                    operator=item.operator,
                    sort_order=sort_order,
                )
                imported += 1
            except Exception as e:
                errors.append(f"行 {item.title}: {e}")
                skipped += 1

        if imported > 0:
            self._activate_compliance_stage(project_id)
            self._propagate_dirty(project_id)

        return RequirementImportResult(
            total=len(parsed), imported=imported, skipped=skipped, errors=errors,
        )

    def export_requirements(self, project_id: str, output_path: str) -> str:
        rows = self.repo.list_by_project(project_id)
        return self.engine.export_requirements_template(rows, output_path)

    # ---- 私有方法 ----

    def _generate_code(self, project_id: str) -> str:
        count = self.repo.count_by_project(project_id)
        return f"REQ-{count + 1:03d}"

    def _activate_compliance_stage(self, project_id: str) -> None:
        """首次新增需求项时激活符合性阶段"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE projects SET compliance_status = 'pending', updated_at = ?
                   WHERE id = ? AND compliance_status = 'skipped'""",
                (now, project_id),
            )

    def _deactivate_compliance_stage(self, project_id: str) -> None:
        """删除所有需求项后恢复 skipped"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET compliance_status = 'skipped', updated_at = ? WHERE id = ?",
                (now, project_id),
            )

    def _propagate_dirty(self, project_id: str) -> None:
        """需求变更 → compliance dirty → comparison dirty"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE projects
                   SET compliance_status = CASE
                         WHEN compliance_status = 'skipped' THEN 'skipped'
                         ELSE 'dirty'
                       END,
                       comparison_status = 'dirty',
                       updated_at = ?
                   WHERE id = ?""",
                (now, project_id),
            )

    def _to_response(self, row: dict) -> RequirementResponse:
        return RequirementResponse(
            id=row["id"],
            project_id=row["project_id"],
            code=row.get("code"),
            category=row["category"],
            title=row["title"],
            description=row.get("description"),
            is_mandatory=bool(row.get("is_mandatory", 1)),
            match_type=row["match_type"],
            expected_value=row.get("expected_value"),
            operator=row.get("operator"),
            sort_order=row.get("sort_order", 0),
            created_at=row["created_at"],
        )
```

### api/requirements.py

**注意：** `RequirementUpdate` 必须包含 `project_id` 字段（在 Task 4.11 Pydantic 模型中定义）。`delete_requirement` 通过查询参数 `?project_id=xxx` 传入。

```python
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from models.compliance import (
    RequirementCreate, RequirementUpdate, RequirementResponse,
    RequirementImportResult,
)
from services.compliance_service import ComplianceService
from api.deps import get_project_db, get_app_data_dir
import tempfile
import shutil

router = APIRouter(tags=["需求标准"])


def _get_service(project_id: str) -> ComplianceService:
    db = get_project_db(project_id)
    return ComplianceService(db)


@router.post("/projects/{project_id}/requirements", response_model=RequirementResponse)
async def create_requirement(project_id: str, req: RequirementCreate):
    service = _get_service(project_id)
    return service.create_requirement(project_id, req)


@router.get("/projects/{project_id}/requirements", response_model=list[RequirementResponse])
async def list_requirements(project_id: str):
    service = _get_service(project_id)
    return service.list_requirements(project_id)


@router.put("/requirements/{req_id}", response_model=RequirementResponse)
async def update_requirement(req_id: str, req: RequirementUpdate):
    """更新需求项。请求体含 project_id"""
    service = _get_service(req.project_id)
    item = service.repo.get_by_id(req_id)
    if not item:
        raise HTTPException(status_code=404, detail="需求项不存在")
    try:
        return service.update_requirement(req_id, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/requirements/{req_id}")
async def delete_requirement(req_id: str, project_id: str):
    """删除需求项。project_id 通过查询参数传入"""
    service = _get_service(project_id)
    item = service.repo.get_by_id(req_id)
    if not item:
        raise HTTPException(status_code=404, detail="需求项不存在")
    deleted = service.delete_requirement(req_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="需求项不存在")
    return {"detail": "已删除"}


@router.post("/projects/{project_id}/requirements/import", response_model=RequirementImportResult)
async def import_requirements(project_id: str, file: UploadFile = File(...)):
    """从模板 Excel 导入需求标准"""
    # 保存上传文件到临时目录
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        service = _get_service(project_id)
        return service.import_requirements(project_id, tmp_path)
    finally:
        import os
        os.unlink(tmp_path)


@router.get("/projects/{project_id}/requirements/export")
async def export_requirements(project_id: str):
    """导出需求标准模板 Excel"""
    app_data = get_app_data_dir()
    output_path = str(app_data / "projects" / project_id / "exports" / "requirements_template.xlsx")
    service = _get_service(project_id)
    service.export_requirements(project_id, output_path)
    return FileResponse(output_path, filename="需求标准模板.xlsx")


```

### main.py 修改

追加路由注册：

```python
from api.requirements import router as requirements_router
app.include_router(requirements_router, prefix="/api")
```

## 测试与验收

### tests/test_requirement_repo.py

```python
import pytest
import uuid


class TestRequirementRepo:
    def test_insert_and_get(self, project_db):
        from db.requirement_repo import RequirementRepo
        repo = RequirementRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            req_id=rid, project_id="p1", code="REQ-001",
            category="技术规格", title="内存>=16GB", description="内存不低于16GB",
            is_mandatory=True, match_type="numeric",
            expected_value="16", operator="gte", sort_order=1,
        )
        row = repo.get_by_id(rid)
        assert row is not None
        assert row["title"] == "内存>=16GB"
        assert row["match_type"] == "numeric"
        assert row["is_mandatory"] == 1

    def test_list_by_project_ordered(self, project_db):
        from db.requirement_repo import RequirementRepo
        repo = RequirementRepo(project_db)
        for i in range(3):
            repo.insert(
                req_id=str(uuid.uuid4()), project_id="p1",
                code=f"REQ-{i+1:03d}", category="功能要求",
                title=f"需求{i+1}", description=None,
                is_mandatory=True, match_type="keyword",
                expected_value=None, operator=None, sort_order=i,
            )
        rows = repo.list_by_project("p1")
        assert len(rows) == 3
        assert rows[0]["code"] == "REQ-001"

    def test_update(self, project_db):
        from db.requirement_repo import RequirementRepo
        repo = RequirementRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            req_id=rid, project_id="p1", code="REQ-001",
            category="功能要求", title="原标题", description=None,
            is_mandatory=True, match_type="keyword",
            expected_value=None, operator=None, sort_order=0,
        )
        repo.update(rid, {"title": "新标题", "is_mandatory": 0})
        row = repo.get_by_id(rid)
        assert row["title"] == "新标题"
        assert row["is_mandatory"] == 0

    def test_delete(self, project_db):
        from db.requirement_repo import RequirementRepo
        repo = RequirementRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            req_id=rid, project_id="p1", code="REQ-001",
            category="功能要求", title="删除测试", description=None,
            is_mandatory=True, match_type="manual",
            expected_value=None, operator=None, sort_order=0,
        )
        assert repo.delete(rid) is True
        assert repo.get_by_id(rid) is None

    def test_count_by_project(self, project_db):
        from db.requirement_repo import RequirementRepo
        repo = RequirementRepo(project_db)
        assert repo.count_by_project("p1") == 0
        repo.insert(
            req_id=str(uuid.uuid4()), project_id="p1", code="REQ-001",
            category="功能要求", title="test", description=None,
            is_mandatory=True, match_type="keyword",
            expected_value=None, operator=None, sort_order=0,
        )
        assert repo.count_by_project("p1") == 1
```

### tests/test_requirements_api.py

```python
import pytest


class TestRequirementsAPI:
    @pytest.mark.anyio
    async def test_create_requirement(self, client_with_project, project_id):
        resp = await client_with_project.post(
            f"/api/projects/{project_id}/requirements",
            json={
                "category": "技术规格",
                "title": "内存>=16GB",
                "match_type": "numeric",
                "expected_value": "16",
                "operator": "gte",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "内存>=16GB"
        assert data["match_type"] == "numeric"
        assert data["code"].startswith("REQ-")

    @pytest.mark.anyio
    async def test_list_requirements(self, client_with_requirements, project_id):
        resp = await client_with_requirements.get(f"/api/projects/{project_id}/requirements")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.anyio
    async def test_update_requirement(self, client_with_requirements, first_req_id, project_id):
        resp = await client_with_requirements.put(
            f"/api/requirements/{first_req_id}",
            json={"project_id": project_id, "title": "修改后标题"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "修改后标题"

    @pytest.mark.anyio
    async def test_delete_requirement(self, client_with_requirements, first_req_id, project_id):
        resp = await client_with_requirements.delete(
            f"/api/requirements/{first_req_id}",
            params={"project_id": project_id},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, client_with_project, project_id):
        resp = await client_with_project.delete(
            "/api/requirements/nonexistent",
            params={"project_id": project_id},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_compliance_stage_activation(self, client_with_project, project_id):
        """创建需求项后 compliance_status 从 skipped 变为 pending"""
        await client_with_project.post(
            f"/api/projects/{project_id}/requirements",
            json={"category": "功能要求", "title": "test", "match_type": "manual"},
        )
        resp = await client_with_project.get(f"/api/projects/{project_id}")
        assert resp.json()["stage_statuses"]["compliance_status"] != "skipped"

    @pytest.mark.anyio
    async def test_invalid_category(self, client_with_project, project_id):
        resp = await client_with_project.post(
            f"/api/projects/{project_id}/requirements",
            json={"category": "无效分类", "title": "test", "match_type": "manual"},
        )
        assert resp.status_code == 422
```

### 门禁命令

```bash
cd backend
ruff check db/requirement_repo.py engines/compliance_evaluator.py services/compliance_service.py api/requirements.py
mypy db/requirement_repo.py engines/compliance_evaluator.py services/compliance_service.py api/requirements.py --ignore-missing-imports
pytest tests/test_requirement_repo.py tests/test_requirements_api.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| 插入需求项 → 可查询 | title, match_type 正确 |
| 列表按 sort_order 排序 | 顺序正确 |
| 更新需求项 → 字段变更 | 200 |
| 删除需求项 → 404 查不到 | 200 |
| 创建需求 → compliance_status 激活 | != skipped |
| 无效 category → 422 | 422 |
| 删除不存在 → 404 | 404 |

## 提交

```bash
git add backend/db/requirement_repo.py backend/engines/compliance_evaluator.py \
       backend/services/compliance_service.py backend/api/requirements.py \
       backend/main.py \
       backend/tests/test_requirement_repo.py backend/tests/test_requirements_api.py
git commit -m "Phase 4.1: 需求标准 CRUD + 导入导出 — RequirementRepo + ComplianceEvaluator(解析) + ComplianceService + API"
```

## Review Notes（审查发现的 Medium/Low 问题）

### 实现约束（开发时必须处理）

- **[M3] `export_requirements` 需创建导出目录**：`output_path` 的父目录可能不存在，实现时须在写文件前调用 `Path(output_path).parent.mkdir(parents=True, exist_ok=True)`。

### Reviewer 提醒

- **[Low] `_generate_code` 并发风险**：通过 `count_by_project + 1` 生成编号，批量导入时若并发调用可能生成重复编号。MVP 可接受，后续版本可改用数据库序列或 UUID 编号。
