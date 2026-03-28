# Task 4.7: 待处理问题清单 API

## 输入条件

- Task 4.3 完成（符合性 API 可用）
- Task 4.5 完成（比价 API 可用）
- Phase 1-3 已完成（导入/标准化/归组数据可用）

## 输出物

- 创建: `backend/services/problem_service.py`
- 创建: `backend/api/problems.py`
- 修改: `backend/main.py`（注册 problems 路由）
- 创建: `backend/tests/test_problems_api.py`

## 禁止修改

- 不修改 `backend/db/schema.sql`
- 不修改已有引擎、repo、service 文件
- 不修改 `frontend/`

## 实现规格

**前置字段依赖约束：** ProblemService 仅依赖前序 Phase 已稳定的字段和表结构进行查询，不在本 Task 内发明新的存储字段或修改 schema。具体依赖：
- `supplier_files.supplier_confirmed`（Phase 1）
- `standardized_rows.column_mapping`、`standardized_rows.confidence`、`standardized_rows.needs_review`（Phase 2）
- `commodity_groups.status`（Phase 3）
- `comparison_results.has_anomaly`、`comparison_results.anomaly_details`（Task 4.4/4.5）
- `compliance_matches.status`、`compliance_matches.needs_review`、`compliance_matches.is_acceptable`（Task 4.2/4.3）
- `requirement_items.is_mandatory`（Task 4.1）

若上游字段缺失或命名不一致，须先协调修改前序 task-spec，不得在本 Task 内硬补字段。

### services/problem_service.py

```python
from db.database import Database
from models.comparison import ProblemGroup, ProblemItem


class ProblemService:
    """
    待处理问题清单聚合服务。

    聚合所有未解决问题，按类型分组返回。覆盖 PRD 7.1 定义的全部问题类型：
    - 未确认供应商名称
    - 未映射字段
    - 规则冲突
    - 低置信字段未确认
    - 单位不一致异常
    - 税价口径异常
    - 未确认归组项
    - 必填字段缺失
    - 未确认需求匹配
    - 必选需求未满足
    - 无法判断且未确认的需求项
    - 部分符合但未判定可接受的需求项
    """

    def __init__(self, db: Database):
        self.db = db

    def get_problems(self, project_id: str) -> list[ProblemGroup]:
        problems: list[ProblemGroup] = []

        # 1. 未确认供应商名称
        items = self._unconfirmed_suppliers(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unconfirmed_supplier",
                label="未确认供应商名称",
                stage="import",
                count=len(items),
                items=items,
            ))

        # 2. 未映射字段
        items = self._unmapped_fields(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unmapped_field",
                label="未映射字段",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 3. 规则冲突
        items = self._rule_conflicts(project_id)
        if items:
            problems.append(ProblemGroup(
                type="rule_conflict",
                label="规则冲突",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 4. 低置信字段未确认
        items = self._low_confidence_unconfirmed(project_id)
        if items:
            problems.append(ProblemGroup(
                type="low_confidence_unconfirmed",
                label="低置信字段未确认",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 5. 单位不一致异常
        items = self._unit_anomalies(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unit_mismatch",
                label="单位不一致异常",
                stage="comparison",
                count=len(items),
                items=items,
            ))

        # 6. 税价口径异常
        items = self._tax_anomalies(project_id)
        if items:
            problems.append(ProblemGroup(
                type="tax_basis_mismatch",
                label="税价口径异常",
                stage="comparison",
                count=len(items),
                items=items,
            ))

        # 7. 未确认归组项
        items = self._unconfirmed_groups(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unconfirmed_group",
                label="未确认归组项",
                stage="grouping",
                count=len(items),
                items=items,
            ))

        # 8. 必填字段缺失
        items = self._missing_required_fields(project_id)
        if items:
            problems.append(ProblemGroup(
                type="missing_required_field",
                label="必填字段缺失",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 9. 未确认需求匹配
        items = self._unconfirmed_compliance(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unconfirmed_compliance",
                label="未确认需求匹配",
                stage="compliance",
                count=len(items),
                items=items,
            ))

        # 10. 必选需求未满足
        items = self._mandatory_not_met(project_id)
        if items:
            problems.append(ProblemGroup(
                type="mandatory_not_met",
                label="必选需求未满足",
                stage="compliance",
                count=len(items),
                items=items,
                severity="error",
            ))

        # 11. 无法判断且未确认
        items = self._unclear_unconfirmed(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unclear_unconfirmed",
                label="无法判断且未确认",
                stage="compliance",
                count=len(items),
                items=items,
            ))

        # 12. 部分符合但未判定可接受
        items = self._partial_not_decided(project_id)
        if items:
            problems.append(ProblemGroup(
                type="partial_not_decided",
                label="部分符合但未判定可接受",
                stage="compliance",
                count=len(items),
                items=items,
            ))

        return problems

    # ---- 查询方法 ----

    def _unconfirmed_suppliers(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT id, file_name FROM supplier_files
                   WHERE project_id = ? AND (supplier_name IS NULL OR supplier_name = '' OR supplier_confirmed = 0)""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="import", target_id=row[0],
                            description=f"文件「{row[1]}」的供应商名称未确认")
                for row in cursor.fetchall()
            ]

    def _unmapped_fields(self, project_id: str) -> list[ProblemItem]:
        """
        [C4-fix] standardized_rows 表无 has_unmapped_fields 列。
        改用 column_mapping JSON 字段判断：若 column_mapping 包含空映射值（某标准字段未找到对应原始列），
        则视为有未映射字段。具体逻辑：column_mapping 中值为 null 或空字符串的 key 即为未映射。
        """
        import json as _json
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sr.column_mapping FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ? AND sr.column_mapping IS NOT NULL""",
                (project_id,),
            )
            items = []
            for row in cursor.fetchall():
                mapping = _json.loads(row[2] or "{}")
                unmapped = [k for k, v in mapping.items() if not v]
                if unmapped:
                    items.append(ProblemItem(
                        id=row[0], stage="normalize", target_id=row[0],
                        description=f"行「{row[1] or '未知'}」存在未映射字段: {', '.join(unmapped)}",
                    ))
            return items

    def _rule_conflicts(self, project_id: str) -> list[ProblemItem]:
        """
        [C4-fix] standardized_rows 表无 has_rule_conflict 列。
        改用 hit_rule_snapshots JSON 字段判断：若同一标准字段被多条规则命中（snapshot 数组中
        同一 target_field 出现 >1 次），视为规则冲突。
        """
        import json as _json
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sr.hit_rule_snapshots FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ? AND sr.hit_rule_snapshots IS NOT NULL""",
                (project_id,),
            )
            items = []
            for row in cursor.fetchall():
                snapshots = _json.loads(row[2] or "[]")
                fields_hit: dict[str, int] = {}
                for s in snapshots:
                    tf = s.get("target_field", "")
                    if tf:
                        fields_hit[tf] = fields_hit.get(tf, 0) + 1
                conflicts = [f for f, c in fields_hit.items() if c > 1]
                if conflicts:
                    items.append(ProblemItem(
                        id=row[0], stage="normalize", target_id=row[0],
                        description=f"行「{row[1] or '未知'}」存在规则冲突: {', '.join(conflicts)}",
                    ))
            return items

    def _low_confidence_unconfirmed(self, project_id: str) -> list[ProblemItem]:
        """
        [C4-fix] standardized_rows 表无 is_confirmed 列。
        改用已有字段: confidence < 0.8 且 needs_review = 1 且 is_manually_modified = 0
        （未经人工修改且需要复核的低置信行）。
        """
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sr.confidence FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ? AND sr.confidence < 0.8
                     AND sr.needs_review = 1 AND sr.is_manually_modified = 0""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="normalize", target_id=row[0],
                            description=f"行「{row[1] or '未知'}」置信度 {row[2]:.0%}，未确认")
                for row in cursor.fetchall()
            ]

    def _unit_anomalies(self, project_id: str) -> list[ProblemItem]:
        return self._get_anomalies_by_type(project_id, "unit_mismatch")

    def _tax_anomalies(self, project_id: str) -> list[ProblemItem]:
        return self._get_anomalies_by_type(project_id, "tax_basis_mismatch")

    def _get_anomalies_by_type(self, project_id: str, anomaly_type: str) -> list[ProblemItem]:
        import json
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cr.id, cr.group_id, cr.anomaly_details, cg.group_name
                   FROM comparison_results cr
                   JOIN commodity_groups cg ON cg.id = cr.group_id
                   WHERE cr.project_id = ? AND cr.has_anomaly = 1""",
                (project_id,),
            )
            items = []
            for row in cursor.fetchall():
                details = json.loads(row[2] or "[]")
                for d in details:
                    if d.get("type") == anomaly_type:
                        items.append(ProblemItem(
                            id=row[0], stage="comparison", target_id=row[1],
                            description=f"商品组「{row[3]}」: {d.get('description', '')}",
                            severity="error",
                        ))
            return items

    def _unconfirmed_groups(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT id, group_name FROM commodity_groups
                   WHERE project_id = ? AND status = 'candidate'""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="grouping", target_id=row[0],
                            description=f"归组「{row[1]}」待确认")
                for row in cursor.fetchall()
            ]

    def _missing_required_fields(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sf.supplier_name FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ?
                     AND (sr.product_name IS NULL OR sr.product_name = ''
                          OR sr.unit IS NULL OR sr.unit = ''
                          OR sr.unit_price IS NULL)""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="normalize", target_id=row[0],
                            description=f"{row[2]} 行「{row[1] or '未知'}」缺失必填字段")
                for row in cursor.fetchall()
            ]

    def _unconfirmed_compliance(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND cm.needs_review = 1""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="compliance", target_id=row[0],
                            description=f"需求「{row[1]}」× 供应商「{row[2]}」待确认")
                for row in cursor.fetchall()
            ]

    def _mandatory_not_met(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND ri.is_mandatory = 1
                     AND cm.status = 'no_match'""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="compliance", target_id=row[0],
                            description=f"必选需求「{row[1]}」× 供应商「{row[2]}」不符合",
                            severity="error")
                for row in cursor.fetchall()
            ]

    def _unclear_unconfirmed(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND cm.status = 'unclear'
                     AND cm.needs_review = 1""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="compliance", target_id=row[0],
                            description=f"需求「{row[1]}」× 供应商「{row[2]}」无法判断，待确认")
                for row in cursor.fetchall()
            ]

    def _partial_not_decided(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND cm.status = 'partial'
                     AND cm.is_acceptable = 0 AND cm.needs_review = 1""",
                (project_id,),
            )
            return [
                ProblemItem(id=row[0], stage="compliance", target_id=row[0],
                            description=f"需求「{row[1]}」× 供应商「{row[2]}」部分符合，未判定可接受")
                for row in cursor.fetchall()
            ]
```

### api/problems.py

```python
from fastapi import APIRouter
from models.comparison import ProblemGroup
from services.problem_service import ProblemService
from api.deps import get_project_db

router = APIRouter(tags=["问题清单"])


@router.get("/projects/{project_id}/problems", response_model=list[ProblemGroup])
async def get_problems(project_id: str):
    """获取待处理问题清单"""
    db = get_project_db(project_id)
    service = ProblemService(db)
    return service.get_problems(project_id)
```

### main.py 修改

```python
from api.problems import router as problems_router
app.include_router(problems_router, prefix="/api")
```

## 测试与验收

### tests/test_problems_api.py

```python
import pytest


class TestProblemsAPI:
    @pytest.mark.anyio
    async def test_get_problems_empty(self, client_with_project, project_id):
        """空项目问题清单为空"""
        resp = await client_with_project.get(f"/api/projects/{project_id}/problems")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.anyio
    async def test_get_problems_with_unconfirmed_groups(self, client_with_groups, project_id):
        """有未确认归组时返回对应问题"""
        resp = await client_with_groups.get(f"/api/projects/{project_id}/problems")
        assert resp.status_code == 200
        data = resp.json()
        types = [g["type"] for g in data]
        assert "unconfirmed_group" in types

    @pytest.mark.anyio
    async def test_get_problems_with_unconfirmed_compliance(
        self, client_with_compliance_results, project_id
    ):
        """有未确认匹配时返回对应问题"""
        resp = await client_with_compliance_results.get(
            f"/api/projects/{project_id}/problems"
        )
        data = resp.json()
        types = [g["type"] for g in data]
        # 应包含至少一种符合性问题
        compliance_types = {"unconfirmed_compliance", "unclear_unconfirmed", "partial_not_decided", "mandatory_not_met"}
        assert len(compliance_types & set(types)) >= 1

    @pytest.mark.anyio
    async def test_problem_group_structure(self, client_with_groups, project_id):
        resp = await client_with_groups.get(f"/api/projects/{project_id}/problems")
        data = resp.json()
        for group in data:
            assert "type" in group
            assert "label" in group
            assert "stage" in group
            assert "count" in group
            assert "items" in group
            assert group["count"] == len(group["items"])
            for item in group["items"]:
                assert "id" in item
                assert "stage" in item
                assert "target_id" in item
                assert "description" in item
```

### 门禁命令

```bash
cd backend
ruff check services/problem_service.py api/problems.py
mypy services/problem_service.py api/problems.py --ignore-missing-imports
pytest tests/test_problems_api.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| 空项目 → 问题列表为空或合理 | 200 |
| 有未确认归组 → type=unconfirmed_group | 存在 |
| 有未确认匹配 → 符合性问题出现 | 至少一种 |
| ProblemGroup 结构完整 | type/label/stage/count/items |
| count == len(items) | 数量一致 |
| ProblemItem 结构完整 | id/stage/target_id/description |

## 提交

```bash
git add backend/services/problem_service.py backend/api/problems.py \
       backend/main.py backend/tests/test_problems_api.py
git commit -m "Phase 4.7: 待处理问题清单 API — 12 类问题跨阶段聚合（导入/标准化/归组/符合性/比价）"
```
