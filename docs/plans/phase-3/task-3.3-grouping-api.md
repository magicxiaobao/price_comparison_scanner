# Task 3.3: 归组 API（生成 + 确认 + 拆分 + 合并）

## 输入条件

- Task 3.2 完成（CommodityGrouper 引擎可用）
- Task 3.4 完成（归组 Pydantic 模型已定义）
- TaskManager 异步框架可用（Phase 1 已建好）
- 数据库 `commodity_groups` + `group_members` 表结构已就绪（Phase 0 建表）

## 输出物

- 创建: `backend/db/group_repo.py`
- 创建: `backend/services/grouping_service.py`
- 创建: `backend/api/grouping.py`
- 修改: `backend/main.py`（注册 grouping 路由）
- 创建: `backend/tests/test_group_repo.py`
- 创建: `backend/tests/test_grouping_api.py`

## 禁止修改

- 不修改 `backend/db/schema.sql`
- 不修改 `backend/engines/commodity_grouper.py`（已稳定）
- 不修改 `backend/models/grouping.py`（已稳定）
- 不修改已有的其他 API 路由文件
- 不修改 `frontend/`

## 实现规格

**分层职责约束：**
- `GroupRepo`：纯数据访问层，只做 SQL 操作
- `GroupingService`：业务编排层，协调 CommodityGrouper 引擎 + GroupRepo + 失效传播
- `api/grouping.py`：路由层，仅做请求解析和响应组装

**service 层禁止直接执行 SQL 语句**，必须通过 repo 方法操作数据库。

### db/group_repo.py

```python
from db.database import Database
from typing import Optional
from datetime import datetime, timezone


class GroupRepo:
    """commodity_groups + group_members 表操作 — 纯数据访问层"""

    def __init__(self, db: Database):
        self.db = db

    def insert_group(
        self,
        group_id: str,
        project_id: str,
        group_name: str,
        normalized_key: str,
        confidence_level: str,
        engine_versions: str,
        match_score: float,
        match_reason: str,
        status: str = "candidate",
    ) -> dict:
        """插入一条归组记录"""
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO commodity_groups
                   (id, project_id, group_name, normalized_key, confidence_level,
                    engine_versions, match_score, match_reason, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (group_id, project_id, group_name, normalized_key,
                 confidence_level, engine_versions, match_score, match_reason, status),
            )
        return self.get_group_by_id(group_id)

    def add_member(self, group_id: str, standardized_row_id: str) -> None:
        """添加归组成员"""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id, standardized_row_id) VALUES (?, ?)",
                (group_id, standardized_row_id),
            )

    def add_members(self, group_id: str, row_ids: list[str]) -> None:
        """批量添加归组成员"""
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO group_members (group_id, standardized_row_id) VALUES (?, ?)",
                [(group_id, rid) for rid in row_ids],
            )

    def get_group_by_id(self, group_id: str) -> Optional[dict]:
        """查询单个归组（不含成员）"""
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM commodity_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_group_members(self, group_id: str) -> list[dict]:
        """查询归组成员（JOIN standardized_rows + supplier_files 获取摘要信息）"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT gm.standardized_row_id,
                          sr.product_name, sr.spec_model, sr.unit,
                          sr.unit_price, sr.quantity, sr.confidence,
                          sf.supplier_name
                   FROM group_members gm
                   JOIN standardized_rows sr ON sr.id = gm.standardized_row_id
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE gm.group_id = ?""",
                (group_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_groups_by_project(self, project_id: str) -> list[dict]:
        """查询项目所有归组，按置信度排序（high > medium > low）"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM commodity_groups
                   WHERE project_id = ?
                   ORDER BY
                     CASE confidence_level
                       WHEN 'high' THEN 1
                       WHEN 'medium' THEN 2
                       WHEN 'low' THEN 3
                     END,
                     match_score DESC""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_status(self, group_id: str, status: str, confirmed_at: str | None = None) -> None:
        """更新归组状态"""
        with self.db.transaction() as conn:
            if confirmed_at:
                conn.execute(
                    "UPDATE commodity_groups SET status = ?, confirmed_at = ? WHERE id = ?",
                    (status, confirmed_at, group_id),
                )
            else:
                conn.execute(
                    "UPDATE commodity_groups SET status = ? WHERE id = ?",
                    (status, group_id),
                )

    def delete_group(self, group_id: str) -> None:
        """删除归组（CASCADE 会自动删除 group_members）"""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM commodity_groups WHERE id = ?", (group_id,))

    def delete_groups_by_project(self, project_id: str) -> int:
        """删除项目所有归组（重新生成前调用），返回删除数量"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM commodity_groups WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount

    def remove_member(self, group_id: str, standardized_row_id: str) -> None:
        """移除归组成员"""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM group_members WHERE group_id = ? AND standardized_row_id = ?",
                (group_id, standardized_row_id),
            )
```

### services/grouping_service.py

```python
import json
import uuid
from datetime import datetime, timezone
from db.database import Database
from db.group_repo import GroupRepo
from engines.commodity_grouper import CommodityGrouper, CandidateGroup
from models.grouping import (
    CommodityGroupResponse, GroupMemberSummary,
    GroupConfirmResponse, GroupSplitResponse,
    GroupMergeResponse, GroupMarkNotComparableResponse,
    GroupMoveMemberResponse,
)

ENGINE_VERSION = "commodity_grouper:1.0"


class GroupingService:
    """归组业务编排 — 协调 CommodityGrouper 引擎 + GroupRepo + 失效传播"""

    def __init__(self, db: Database):
        self.db = db
        self.repo = GroupRepo(db)
        self.engine = CommodityGrouper()

    def generate_candidates(self, progress_callback: object, project_id: str) -> list[CommodityGroupResponse]:
        """
        生成候选归组。

        1. 清除该项目已有归组
        2. 从 standardized_rows 查询所有已标准化的行
        3. 调用 CommodityGrouper.generate_candidates()
        4. 将结果写入 commodity_groups + group_members
        5. 更新项目阶段状态
        6. 返回归组列表
        """
        # 清除旧归组
        self.repo.delete_groups_by_project(project_id)
        progress_callback(0.1)

        # 查询标准化行
        rows = self._get_standardized_rows(project_id)
        if not rows:
            return []

        # 生成候选
        candidates = self.engine.generate_candidates(rows)
        progress_callback(0.5)

        # 持久化
        result: list[CommodityGroupResponse] = []
        for candidate in candidates:
            group_id = str(uuid.uuid4())
            self.repo.insert_group(
                group_id=group_id,
                project_id=project_id,
                group_name=candidate.group_name,
                normalized_key=candidate.normalized_key,
                confidence_level=candidate.confidence_level,
                engine_versions=json.dumps({"grouper": ENGINE_VERSION}),
                match_score=candidate.match_score,
                match_reason=candidate.match_reason,
            )
            self.repo.add_members(group_id, candidate.member_row_ids)
            result.append(self._to_response(group_id, project_id))

        progress_callback(1.0)

        # 更新阶段状态
        self._update_stage_status(project_id, "grouping_status", "completed")

        return result

    def list_groups(self, project_id: str) -> list[CommodityGroupResponse]:
        """获取项目所有归组"""
        groups = self.repo.list_groups_by_project(project_id)
        return [self._to_response(g["id"], project_id) for g in groups]

    def confirm_group(self, group_id: str) -> GroupConfirmResponse:
        """确认归组"""
        now = datetime.now(timezone.utc).isoformat()
        self.repo.update_status(group_id, "confirmed", confirmed_at=now)

        group = self.repo.get_group_by_id(group_id)
        # 触发失效传播
        self._propagate_dirty(group["project_id"])

        return GroupConfirmResponse(id=group_id, status="confirmed", confirmed_at=now)

    def split_group(self, group_id: str, new_groups_row_ids: list[list[str]]) -> GroupSplitResponse:
        """
        拆分归组。

        1. 验证原组存在
        2. 验证 row_ids 都属于原组
        3. 删除原组
        4. 为每个子组创建新归组
        5. 触发失效传播
        """
        original = self.repo.get_group_by_id(group_id)
        if not original:
            raise ValueError(f"归组不存在: {group_id}")

        project_id = original["project_id"]

        # 删除原组
        self.repo.delete_group(group_id)

        # 创建新组
        new_responses: list[CommodityGroupResponse] = []
        for row_ids in new_groups_row_ids:
            new_id = str(uuid.uuid4())
            self.repo.insert_group(
                group_id=new_id,
                project_id=project_id,
                group_name=original["group_name"],
                normalized_key=original["normalized_key"],
                confidence_level="medium",  # 拆分后降为 medium
                engine_versions=original["engine_versions"],
                match_score=0.0,
                match_reason=f"从归组 {group_id[:8]} 拆分",
                status="candidate",
            )
            self.repo.add_members(new_id, row_ids)
            new_responses.append(self._to_response(new_id, project_id))

        # 触发失效传播
        self._propagate_dirty(project_id)

        return GroupSplitResponse(
            original_group_id=group_id,
            new_groups=new_responses,
        )

    def merge_groups(self, project_id: str, group_ids: list[str]) -> GroupMergeResponse:
        """
        合并归组。

        1. 收集所有成员 row_ids
        2. 取第一个组作为合并目标
        3. 删除其余组
        4. 将所有成员加入目标组
        5. 触发失效传播
        """
        all_row_ids: list[str] = []
        first_group = None

        for gid in group_ids:
            group = self.repo.get_group_by_id(gid)
            if not group:
                raise ValueError(f"归组不存在: {gid}")
            members = self.repo.get_group_members(gid)
            all_row_ids.extend(m["standardized_row_id"] for m in members)
            if first_group is None:
                first_group = group

        # 删除所有组
        for gid in group_ids:
            self.repo.delete_group(gid)

        # 创建合并后的新组
        merged_id = str(uuid.uuid4())
        self.repo.insert_group(
            group_id=merged_id,
            project_id=project_id,
            group_name=first_group["group_name"],
            normalized_key=first_group["normalized_key"],
            confidence_level="medium",  # 手工合并默认 medium
            engine_versions=first_group["engine_versions"],
            match_score=0.0,
            match_reason=f"手工合并 {len(group_ids)} 个归组",
            status="candidate",
        )
        # 去重后添加成员
        unique_row_ids = list(dict.fromkeys(all_row_ids))
        self.repo.add_members(merged_id, unique_row_ids)

        # 触发失效传播
        self._propagate_dirty(project_id)

        removed_ids = [gid for gid in group_ids]
        return GroupMergeResponse(
            merged_group=self._to_response(merged_id, project_id),
            removed_group_ids=removed_ids,
        )

    def mark_not_comparable(self, group_id: str) -> GroupMarkNotComparableResponse:
        """标记归组为不可比"""
        self.repo.update_status(group_id, "not_comparable")
        group = self.repo.get_group_by_id(group_id)
        self._propagate_dirty(group["project_id"])
        return GroupMarkNotComparableResponse(id=group_id, status="not_comparable")

    def move_member(self, source_group_id: str, target_group_id: str, row_id: str) -> GroupMoveMemberResponse:
        """
        原子操作：将成员从源组移动到目标组。
        1. 验证源组和目标组都存在
        2. 验证 row_id 属于源组
        3. 验证源组成员数 > 1（不能拖空）
        4. 验证目标组状态允许接收（非 confirmed/not_comparable）
        5. 从源组移除成员
        6. 添加到目标组
        7. 触发失效传播
        """
        source = self.repo.get_group_by_id(source_group_id)
        target = self.repo.get_group_by_id(target_group_id)
        if not source or not target:
            raise ValueError("源组或目标组不存在")

        if target["status"] in ("confirmed", "not_comparable"):
            raise ValueError(f"目标组状态为 {target['status']}，不接受新成员")

        source_members = self.repo.get_group_members(source_group_id)
        if len(source_members) <= 1:
            raise ValueError("源组仅剩 1 个成员，不可移出")

        member_ids = [m["standardized_row_id"] for m in source_members]
        if row_id not in member_ids:
            raise ValueError(f"成员 {row_id} 不属于源组 {source_group_id}")

        # 原子移动
        self.repo.remove_member(source_group_id, row_id)
        self.repo.add_member(target_group_id, row_id)

        # 触发失效传播
        self._propagate_dirty(source["project_id"])

        return GroupMoveMemberResponse(
            source_group=self._to_response(source_group_id, source["project_id"]),
            target_group=self._to_response(target_group_id, target["project_id"]),
            moved_row_id=row_id,
        )

    # ---- 私有方法 ----

    def _get_standardized_rows(self, project_id: str) -> list[dict]:
        """查询项目所有标准化行"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.* FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ?""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _to_response(self, group_id: str, project_id: str) -> CommodityGroupResponse:
        """将数据库记录转换为响应模型"""
        group = self.repo.get_group_by_id(group_id)
        members_data = self.repo.get_group_members(group_id)

        members = [
            GroupMemberSummary(
                standardized_row_id=m["standardized_row_id"],
                supplier_name=m.get("supplier_name", ""),
                product_name=m.get("product_name", ""),
                spec_model=m.get("spec_model", ""),
                unit=m.get("unit", ""),
                unit_price=m.get("unit_price"),
                quantity=m.get("quantity"),
                confidence=m.get("confidence", 1.0),
            )
            for m in members_data
        ]

        return CommodityGroupResponse(
            id=group["id"],
            project_id=project_id,
            group_name=group["group_name"],
            normalized_key=group["normalized_key"],
            confidence_level=group["confidence_level"],
            match_score=group["match_score"],
            match_reason=group["match_reason"],
            status=group["status"],
            confirmed_at=group.get("confirmed_at"),
            members=members,
            member_count=len(members),
        )

    _VALID_STAGES = frozenset({
        "import_status", "normalize_status", "grouping_status",
        "compliance_status", "comparison_status",
    })

    def _update_stage_status(self, project_id: str, stage: str, status: str) -> None:
        """更新项目阶段状态"""
        if stage not in self._VALID_STAGES:
            raise ValueError(f"Invalid stage: {stage}")
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {stage} = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now(timezone.utc).isoformat(), project_id),
            )

    def _propagate_dirty(self, project_id: str) -> None:
        """
        失效传播：归组变更 → compliance dirty → comparison dirty

        参考技术架构 4.3：
        修改 commodity_groups（确认/拆分/合并）→ compliance dirty → comparison dirty
        """
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
```

### api/grouping.py

```python
from fastapi import APIRouter, HTTPException, Depends
from models.grouping import (
    CommodityGroupResponse,
    GroupingGenerateResponse,
    GroupActionRequest,
    GroupConfirmResponse,
    GroupSplitRequest, GroupSplitResponse,
    GroupMergeRequest, GroupMergeResponse,
    GroupMarkNotComparableResponse,
    GroupMoveMemberRequest, GroupMoveMemberResponse,
)
from services.grouping_service import GroupingService
from api.deps import get_project_db

router = APIRouter(tags=["商品归组"])


def _get_grouping_service(project_id: str) -> GroupingService:
    db = get_project_db(project_id)
    return GroupingService(db)


@router.post("/projects/{project_id}/grouping/generate", response_model=GroupingGenerateResponse)
async def generate_grouping(project_id: str):
    """生成归组候选（异步任务）"""
    # MVP 简化：同步执行，后续可改为 TaskManager 异步
    # 如需异步，通过 TaskManager.submit() 提交
    from engines.task_manager import get_task_manager
    service = _get_grouping_service(project_id)
    tm = get_task_manager()
    task_id = tm.submit(
        "grouping",
        service.generate_candidates,
        project_id,
    )
    return GroupingGenerateResponse(task_id=task_id)


@router.get("/projects/{project_id}/groups", response_model=list[CommodityGroupResponse])
async def list_groups(project_id: str):
    """获取项目所有归组"""
    service = _get_grouping_service(project_id)
    return service.list_groups(project_id)


@router.put("/groups/{group_id}/confirm", response_model=GroupConfirmResponse)
async def confirm_group(group_id: str, body: GroupActionRequest):
    """确认归组"""
    service = _get_grouping_service(body.project_id)
    group = service.repo.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="归组不存在")
    return service.confirm_group(group_id)


@router.put("/groups/{group_id}/split", response_model=GroupSplitResponse)
async def split_group(group_id: str, req: GroupSplitRequest):
    """拆分归组。请求体含 project_id + new_groups"""
    service = _get_grouping_service(req.project_id)
    group = service.repo.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="归组不存在")
    try:
        return service.split_group(group_id, req.new_groups)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/grouping/merge", response_model=GroupMergeResponse)
async def merge_groups(project_id: str, req: GroupMergeRequest):
    """手工合并归组"""
    service = _get_grouping_service(project_id)
    try:
        return service.merge_groups(project_id, req.group_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/groups/{group_id}/not-comparable", response_model=GroupMarkNotComparableResponse)
async def mark_not_comparable(group_id: str, body: GroupActionRequest):
    """标记归组为不可比"""
    service = _get_grouping_service(body.project_id)
    group = service.repo.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="归组不存在")
    return service.mark_not_comparable(group_id)


@router.put("/groups/{group_id}/move-member", response_model=GroupMoveMemberResponse)
async def move_member(group_id: str, req: GroupMoveMemberRequest):
    """
    将成员从当前归组移动到目标归组（原子操作）。
    前端拖拽完成后调用此 API，无需分两步 split + merge。
    """
    service = _get_grouping_service(req.project_id)
    source = service.repo.get_group_by_id(group_id)
    if not source:
        raise HTTPException(status_code=404, detail="源归组不存在")
    try:
        return service.move_member(group_id, req.target_group_id, req.row_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### main.py 修改

追加路由注册：

```python
from api.grouping import router as grouping_router
app.include_router(grouping_router, prefix="/api")
```

## 测试与验收

### 测试 Fixture（补充到 conftest.py 或本文件 conftest）

本 Task 的测试需要以下 fixture，如果 `conftest.py` 中不存在则需创建：

```python
import uuid
import pytest
from db.database import Database

@pytest.fixture
def project_db(tmp_path) -> Database:
    """创建临时项目数据库，初始化完整 schema"""
    db = Database(tmp_path / "test_project.db")
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    with db.transaction() as conn:
        conn.executescript(schema_path.read_text())
    # 插入测试项目
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("p1", "test-project", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
    return db


@pytest.fixture
def sample_standardized_rows(project_db) -> list[dict]:
    """插入 3 条测试用标准化行，返回行记录列表"""
    rows = []
    with project_db.transaction() as conn:
        # 先插入 supplier_file 和 raw_table
        conn.execute(
            "INSERT INTO supplier_files (id, project_id, original_name, stored_path, file_type, supplier_name, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sf1", "p1", "test.xlsx", "/tmp/test.xlsx", "xlsx", "供应商A", "parsed"),
        )
        conn.execute(
            "INSERT INTO raw_tables (id, supplier_file_id, sheet_name, row_count, column_count, is_selected) VALUES (?, ?, ?, ?, ?, ?)",
            ("rt1", "sf1", "Sheet1", 3, 5, 1),
        )
        for i in range(3):
            row_id = f"sr{i+1}"
            conn.execute(
                """INSERT INTO standardized_rows
                   (id, raw_table_id, supplier_file_id, row_index, product_name, spec_model, unit, quantity, unit_price, source_location)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row_id, "rt1", "sf1", i, f"商品{i+1}", f"规格{i+1}", "台", 10.0, 100.0, "{}"),
            )
            rows.append({"id": row_id, "product_name": f"商品{i+1}", "spec_model": f"规格{i+1}", "unit": "台"})
    return rows
```

**注意**：`test_grouping_api.py` 中引用的 `client_with_standardized_data`、`client_with_groups`、`first_group_id`、`group_with_2_members`、`two_group_ids`、`another_group_id` 等 fixture 需要在实现时根据上述基础 fixture 搭建。task-spec 中的 API 测试为示意结构，具体 fixture 实现由 backend-dev 在编码时补全。

### tests/test_group_repo.py

```python
import pytest
import uuid

# 需要已有的 conftest fixture（temp db, schema init）


class TestGroupRepo:
    def test_insert_and_get(self, project_db):
        from db.group_repo import GroupRepo
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="thinkpad e14", normalized_key="thinkpad e14",
            confidence_level="high", engine_versions='{"grouper":"1.0"}',
            match_score=0.95, match_reason="名称一致",
        )
        group = repo.get_group_by_id(gid)
        assert group is not None
        assert group["group_name"] == "thinkpad e14"
        assert group["confidence_level"] == "high"
        assert group["status"] == "candidate"

    def test_add_and_get_members(self, project_db, sample_standardized_rows):
        from db.group_repo import GroupRepo
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        row_ids = [r["id"] for r in sample_standardized_rows[:2]]
        repo.add_members(gid, row_ids)
        members = repo.get_group_members(gid)
        assert len(members) == 2

    def test_list_groups_ordered(self, project_db):
        from db.group_repo import GroupRepo
        repo = GroupRepo(project_db)
        # 插入 3 个不同置信度的组
        for level in ["low", "high", "medium"]:
            repo.insert_group(
                group_id=str(uuid.uuid4()), project_id="p1",
                group_name=f"group-{level}", normalized_key=f"group-{level}",
                confidence_level=level, engine_versions="{}",
                match_score=0.5, match_reason="test",
            )
        groups = repo.list_groups_by_project("p1")
        levels = [g["confidence_level"] for g in groups]
        assert levels == ["high", "medium", "low"]

    def test_update_status(self, project_db):
        from db.group_repo import GroupRepo
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        repo.update_status(gid, "confirmed", confirmed_at="2026-01-01T00:00:00Z")
        group = repo.get_group_by_id(gid)
        assert group["status"] == "confirmed"
        assert group["confirmed_at"] == "2026-01-01T00:00:00Z"

    def test_delete_group_cascades(self, project_db, sample_standardized_rows):
        from db.group_repo import GroupRepo
        repo = GroupRepo(project_db)
        gid = str(uuid.uuid4())
        repo.insert_group(
            group_id=gid, project_id="p1",
            group_name="test", normalized_key="test",
            confidence_level="high", engine_versions="{}",
            match_score=0.9, match_reason="test",
        )
        repo.add_members(gid, [sample_standardized_rows[0]["id"]])
        repo.delete_group(gid)
        assert repo.get_group_by_id(gid) is None
        # CASCADE: members 也应被删除
        members = repo.get_group_members(gid)
        assert len(members) == 0

    def test_delete_groups_by_project(self, project_db):
        from db.group_repo import GroupRepo
        repo = GroupRepo(project_db)
        for _ in range(3):
            repo.insert_group(
                group_id=str(uuid.uuid4()), project_id="p1",
                group_name="test", normalized_key="test",
                confidence_level="high", engine_versions="{}",
                match_score=0.9, match_reason="test",
            )
        count = repo.delete_groups_by_project("p1")
        assert count == 3
        assert repo.list_groups_by_project("p1") == []
```

### tests/test_grouping_api.py

```python
import pytest


class TestGroupingAPI:
    @pytest.mark.anyio
    async def test_generate_grouping(self, client_with_standardized_data, project_id):
        """生成归组候选"""
        resp = await client_with_standardized_data.post(
            f"/api/projects/{project_id}/grouping/generate",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data

    @pytest.mark.anyio
    async def test_list_groups(self, client_with_groups, project_id):
        """获取归组列表"""
        resp = await client_with_groups.get(f"/api/projects/{project_id}/groups")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for group in data:
            assert group["confidence_level"] in ("high", "medium", "low")
            assert group["status"] in ("candidate", "confirmed", "split", "not_comparable")
            assert "members" in group
            assert "match_reason" in group
            assert isinstance(group["member_count"], int)

    @pytest.mark.anyio
    async def test_confirm_group(self, client_with_groups, project_id, first_group_id):
        """确认归组"""
        resp = await client_with_groups.put(
            f"/api/groups/{first_group_id}/confirm",
            json={"project_id": project_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["confirmed_at"] is not None

    @pytest.mark.anyio
    async def test_split_group(self, client_with_groups, project_id, group_with_2_members):
        """拆分归组"""
        group_id, row_ids = group_with_2_members
        resp = await client_with_groups.put(
            f"/api/groups/{group_id}/split",
            json={"project_id": project_id, "new_groups": [[row_ids[0]], [row_ids[1]]]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["original_group_id"] == group_id
        assert len(data["new_groups"]) == 2

    @pytest.mark.anyio
    async def test_merge_groups(self, client_with_groups, project_id, two_group_ids):
        """合并归组"""
        resp = await client_with_groups.post(
            f"/api/projects/{project_id}/grouping/merge",
            json={"group_ids": two_group_ids},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "merged_group" in data
        assert set(data["removed_group_ids"]) == set(two_group_ids)

    @pytest.mark.anyio
    async def test_mark_not_comparable(self, client_with_groups, project_id, first_group_id):
        """标记不可比"""
        resp = await client_with_groups.put(
            f"/api/groups/{first_group_id}/not-comparable",
            json={"project_id": project_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_comparable"

    @pytest.mark.anyio
    async def test_confirm_nonexistent_group(self, client_with_groups, project_id):
        """确认不存在的归组 → 404"""
        resp = await client_with_groups.put(
            "/api/groups/nonexistent/confirm",
            json={"project_id": project_id},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_dirty_propagation_after_confirm(self, client_with_groups, project_id, first_group_id):
        """确认归组后下游阶段应变为 dirty"""
        await client_with_groups.put(
            f"/api/groups/{first_group_id}/confirm",
            json={"project_id": project_id},
        )
        resp = await client_with_groups.get(f"/api/projects/{project_id}")
        data = resp.json()
        assert data["stage_statuses"]["comparison_status"] == "dirty"

    @pytest.mark.anyio
    async def test_move_member(self, client_with_groups, project_id, group_with_2_members, another_group_id):
        """成员移动"""
        group_id, row_ids = group_with_2_members
        resp = await client_with_groups.put(
            f"/api/groups/{group_id}/move-member",
            json={"project_id": project_id, "target_group_id": another_group_id, "row_id": row_ids[0]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["moved_row_id"] == row_ids[0]
```

### 门禁命令

```bash
cd backend
ruff check db/group_repo.py services/grouping_service.py api/grouping.py
mypy db/group_repo.py services/grouping_service.py api/grouping.py --ignore-missing-imports
pytest tests/test_group_repo.py tests/test_grouping_api.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| 插入归组 → 可查询 | status == "candidate" |
| 归组列表按 high > medium > low 排序 | 顺序正确 |
| 删除归组 → CASCADE 删除成员 | members 为空 |
| POST generate → 返回 task_id | 200 |
| GET groups → 返回列表含 members, match_reason | 200 |
| PUT confirm → status == "confirmed" | 200 |
| PUT split → 产生 2+ 新组 | 200 |
| POST merge → 合并为 1 组 | 200 |
| PUT not-comparable → status == "not_comparable" | 200 |
| 确认后 → comparison_status == "dirty" | 失效传播生效 |
| PUT move-member → 成员移动成功 | 200 |
| move-member 源组仅 1 成员 → 400 | 400 |
| move-member 目标组 confirmed → 400 | 400 |
| 不存在的 group_id → 404 | 404 |

## 提交

```bash
git add backend/db/group_repo.py backend/services/grouping_service.py \
       backend/api/grouping.py backend/main.py \
       backend/tests/test_group_repo.py backend/tests/test_grouping_api.py
git commit -m "Phase 3.3: 归组 API — 生成/确认/拆分/合并/标记不可比 + GroupRepo + GroupingService + 失效传播"
```
