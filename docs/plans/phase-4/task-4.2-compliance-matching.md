# Task 4.2: ComplianceEvaluator — 符合性匹配（keyword/numeric/manual）

## 输入条件

- Task 4.1 完成（ComplianceEvaluator 基础结构 + RequirementRepo 可用）
- 数据库 `compliance_matches` 表结构已就绪（Phase 0 建表）
- 归组数据可用（Phase 3 已完成）
- 标准化数据可用（Phase 2 已完成）

## 输出物

- 修改: `backend/engines/compliance_evaluator.py`（新增 evaluate、_match_keyword、_match_numeric 方法）
- 创建: `backend/db/compliance_repo.py`
- 修改: `backend/services/compliance_service.py`（新增 evaluate、get_matrix、confirm、accept 方法）
- 创建: `backend/tests/test_compliance_evaluator.py`
- 创建: `backend/tests/test_compliance_repo.py`

## 禁止修改

- 不修改 `backend/db/schema.sql`
- 不修改 `backend/models/compliance.py`（已稳定）
- 不修改 `backend/db/requirement_repo.py`（已稳定）
- 不修改 `frontend/`

## 实现规格

### db/compliance_repo.py

```python
from db.database import Database
from typing import Optional
from datetime import datetime, timezone


class ComplianceRepo:
    """compliance_matches 表操作 — 纯数据访问层"""

    def __init__(self, db: Database):
        self.db = db

    def insert(
        self,
        match_id: str,
        requirement_item_id: str,
        commodity_group_id: str,
        supplier_file_id: str,
        status: str,
        is_acceptable: bool,
        match_score: Optional[float],
        evidence_text: Optional[str],
        evidence_location: Optional[str],
        match_method: Optional[str],
        needs_review: bool,
        engine_versions: Optional[str],
    ) -> dict:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO compliance_matches
                   (id, requirement_item_id, commodity_group_id, supplier_file_id,
                    status, is_acceptable, match_score, evidence_text, evidence_location,
                    match_method, needs_review, engine_versions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (match_id, requirement_item_id, commodity_group_id, supplier_file_id,
                 status, 1 if is_acceptable else 0, match_score, evidence_text,
                 evidence_location, match_method, 1 if needs_review else 0, engine_versions),
            )
        return self.get_by_id(match_id)

    def get_by_id(self, match_id: str) -> Optional[dict]:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM compliance_matches WHERE id = ?", (match_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        """通过 requirement_items JOIN 获取项目所有匹配结果"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.*, ri.project_id
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   WHERE ri.project_id = ?""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_by_requirement(self, requirement_item_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM compliance_matches WHERE requirement_item_id = ?",
                (requirement_item_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_by_group_and_supplier(self, group_id: str, supplier_file_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM compliance_matches
                   WHERE commodity_group_id = ? AND supplier_file_id = ?""",
                (group_id, supplier_file_id),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_status(self, match_id: str, status: str, confirmed_at: Optional[str] = None) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE compliance_matches
                   SET status = ?, needs_review = 0, confirmed_at = ?
                   WHERE id = ?""",
                (status, confirmed_at, match_id),
            )

    def update_acceptable(self, match_id: str, is_acceptable: bool) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE compliance_matches SET is_acceptable = ? WHERE id = ?",
                (1 if is_acceptable else 0, match_id),
            )

    def delete_by_project(self, project_id: str) -> int:
        """删除项目所有匹配结果（重新评估前调用）"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """DELETE FROM compliance_matches
                   WHERE requirement_item_id IN
                     (SELECT id FROM requirement_items WHERE project_id = ?)""",
                (project_id,),
            )
            return cursor.rowcount

    def get_eligible_supplier_ids(self, group_id: str) -> list[str]:
        """返回该商品组中有资格参与有效最低价的供应商 ID 列表"""
        with self.db.read() as conn:
            # 检查是否有需求项
            cursor = conn.execute(
                """SELECT DISTINCT cm.supplier_file_id
                   FROM compliance_matches cm
                   WHERE cm.commodity_group_id = ?""",
                (group_id,),
            )
            all_suppliers = [row[0] for row in cursor.fetchall()]
            if not all_suppliers:
                return []  # 无需求标准，由调用方处理

            # 对每个供应商，检查所有必选需求是否满足
            eligible: list[str] = []
            for sid in all_suppliers:
                cursor = conn.execute(
                    """SELECT cm.status, cm.is_acceptable, ri.is_mandatory
                       FROM compliance_matches cm
                       JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                       WHERE cm.commodity_group_id = ? AND cm.supplier_file_id = ?""",
                    (group_id, sid),
                )
                rows = cursor.fetchall()
                is_eligible = True
                for row in rows:
                    status, is_acceptable, is_mandatory = row[0], row[1], row[2]
                    if is_mandatory:
                        if status == "no_match":
                            is_eligible = False
                            break
                        if status == "unclear" and not is_acceptable:
                            is_eligible = False
                            break
                        if status == "partial" and not is_acceptable:
                            is_eligible = False
                            break
                if is_eligible:
                    eligible.append(sid)

            return eligible
```

### engines/compliance_evaluator.py（新增匹配方法）

在 Task 4.1 已创建的文件中追加：

```python
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MatchResult:
    """单条匹配结果"""
    status: str              # match / partial / no_match / unclear
    match_score: float       # 0.0 - 1.0
    evidence_text: str       # 证据原文
    evidence_location: str   # JSON 字符串
    match_method: str        # keyword / numeric / manual
    needs_review: bool       # 是否需人工确认


class ComplianceEvaluator:
    # ... Task 4.1 已有的 parse/export 方法 ...

    ENGINE_VERSION = "compliance_evaluator:1.0"

    def evaluate_single(
        self,
        requirement: dict,
        supplier_rows: list[dict],
        supplier_file_id: str,
    ) -> MatchResult:
        """
        对单个「需求项 × 供应商（该商品组下的行）」执行匹配。

        requirement: requirement_items 表记录
        supplier_rows: 该供应商在该商品组下的标准化行列表
        """
        match_type = requirement["match_type"]

        if match_type == "keyword":
            return self._match_keyword(requirement, supplier_rows)
        elif match_type == "numeric":
            return self._match_numeric(requirement, supplier_rows)
        else:  # manual
            return MatchResult(
                status="unclear",
                match_score=0.0,
                evidence_text="",
                evidence_location="{}",
                match_method="manual",
                needs_review=True,
            )

    def _match_keyword(self, requirement: dict, rows: list[dict]) -> MatchResult:
        """
        keyword 匹配：在标准化数据的 spec_model / remark / product_name 中搜索关键词。
        命中 → 符合；未命中 → 无法判断。
        """
        keyword = (requirement.get("expected_value") or "").strip()
        if not keyword:
            return MatchResult(
                status="unclear", match_score=0.0,
                evidence_text="未设置关键词",
                evidence_location="{}", match_method="keyword",
                needs_review=True,
            )

        search_fields = ["spec_model", "remark", "product_name"]
        for row in rows:
            for field_name in search_fields:
                field_value = str(row.get(field_name, "") or "")
                if keyword.lower() in field_value.lower():
                    return MatchResult(
                        status="match",
                        match_score=1.0,
                        evidence_text=f"在 {field_name} 中找到关键词「{keyword}」: {field_value}",
                        evidence_location="{}",  # 实际实现时填充 source_location
                        match_method="keyword",
                        needs_review=False,
                    )

        return MatchResult(
            status="unclear",
            match_score=0.0,
            evidence_text=f"未在供应商数据中找到关键词「{keyword}」",
            evidence_location="{}",
            match_method="keyword",
            needs_review=True,
        )

    def _match_numeric(self, requirement: dict, rows: list[dict]) -> MatchResult:
        """
        numeric 匹配：提取数值与目标值比较。
        满足 → 符合；不满足 → 不符合；无法提取 → 无法判断。
        """
        expected_str = (requirement.get("expected_value") or "").strip()
        operator = requirement.get("operator", "gte")

        try:
            expected = float(expected_str)
        except (ValueError, TypeError):
            return MatchResult(
                status="unclear", match_score=0.0,
                evidence_text=f"无法解析目标值: {expected_str}",
                evidence_location="{}", match_method="numeric",
                needs_review=True,
            )

        # 在 spec_model / remark / product_name 中搜索数值
        search_fields = ["spec_model", "remark", "product_name"]
        for row in rows:
            for field_name in search_fields:
                field_value = str(row.get(field_name, "") or "")
                numbers = re.findall(r"[\d]+\.?\d*", field_value)
                for num_str in numbers:
                    try:
                        actual = float(num_str)
                    except ValueError:
                        continue

                    satisfied = self._compare_numeric(actual, expected, operator)
                    if satisfied is not None:
                        status = "match" if satisfied else "no_match"
                        return MatchResult(
                            status=status,
                            match_score=1.0 if satisfied else 0.0,
                            evidence_text=f"在 {field_name} 中提取数值 {actual}，"
                                          f"目标 {operator} {expected}",
                            evidence_location="{}",
                            match_method="numeric",
                            needs_review=False,
                        )

        return MatchResult(
            status="unclear",
            match_score=0.0,
            evidence_text=f"未能从供应商数据中提取可比较的数值",
            evidence_location="{}",
            match_method="numeric",
            needs_review=True,
        )

    def _compare_numeric(
        self, actual: float, expected: float, operator: str
    ) -> Optional[bool]:
        if operator == "gte":
            return actual >= expected
        elif operator == "lte":
            return actual <= expected
        elif operator == "eq":
            return abs(actual - expected) < 0.001
        elif operator == "range":
            return None  # range 需要两个值，MVP 简化处理
        return None
```

### services/compliance_service.py（新增匹配方法）

在 Task 4.1 已创建的 ComplianceService 类中追加：

```python
    # ---- 符合性匹配 ----

    def evaluate(self, project_id: str) -> list:
        """
        执行符合性匹配。

        1. 清除该项目已有匹配结果
        2. 获取所有需求项
        3. 获取所有已确认的商品组
        4. 对每个「商品组 × 供应商 × 需求项」执行匹配
        5. 持久化结果
        6. 更新阶段状态
        """
        from db.compliance_repo import ComplianceRepo
        compliance_repo = ComplianceRepo(self.db)

        # 清除旧匹配结果
        compliance_repo.delete_by_project(project_id)

        requirements = self.repo.list_by_project(project_id)
        if not requirements:
            return []

        groups = self._get_confirmed_groups(project_id)
        results = []

        for group in groups:
            supplier_rows_map = self._get_supplier_rows_for_group(group["id"])
            for supplier_file_id, rows in supplier_rows_map.items():
                for req in requirements:
                    match_result = self.engine.evaluate_single(req, rows, supplier_file_id)
                    match_id = str(uuid.uuid4())
                    compliance_repo.insert(
                        match_id=match_id,
                        requirement_item_id=req["id"],
                        commodity_group_id=group["id"],
                        supplier_file_id=supplier_file_id,
                        status=match_result.status,
                        is_acceptable=False,
                        match_score=match_result.match_score,
                        evidence_text=match_result.evidence_text,
                        evidence_location=match_result.evidence_location,
                        match_method=match_result.match_method,
                        needs_review=match_result.needs_review,
                        engine_versions=json.dumps({"evaluator": self.engine.ENGINE_VERSION}),
                    )
                    results.append(match_id)

        self._update_stage_status(project_id, "compliance_status", "completed")
        return results

    def get_matrix(self, project_id: str):
        """获取符合性矩阵"""
        from db.compliance_repo import ComplianceRepo
        from models.compliance import (
            ComplianceMatrixResponse, ComplianceMatrixRow,
            ComplianceMatrixCell, RequirementResponse,
        )
        compliance_repo = ComplianceRepo(self.db)
        requirements = self.repo.list_by_project(project_id)
        matches = compliance_repo.list_by_project(project_id)

        # 获取供应商名称映射
        supplier_names = self._get_supplier_names(project_id)

        # 按需求项组织矩阵
        rows: list[ComplianceMatrixRow] = []
        for req in requirements:
            req_matches = [m for m in matches if m["requirement_item_id"] == req["id"]]
            suppliers: dict[str, ComplianceMatrixCell] = {}
            for m in req_matches:
                suppliers[m["supplier_file_id"]] = ComplianceMatrixCell(
                    match_id=m["id"],
                    status=m["status"],
                    is_acceptable=bool(m.get("is_acceptable", 0)),
                    needs_review=bool(m.get("needs_review", 1)),
                    evidence_text=m.get("evidence_text"),
                )
            rows.append(ComplianceMatrixRow(
                requirement=self._to_response(req),
                suppliers=suppliers,
            ))

        return ComplianceMatrixResponse(supplier_names=supplier_names, rows=rows)

    def confirm_match(self, match_id: str, status: str) -> dict:
        """人工确认匹配结果"""
        from db.compliance_repo import ComplianceRepo
        compliance_repo = ComplianceRepo(self.db)
        now = datetime.now(timezone.utc).isoformat()
        compliance_repo.update_status(match_id, status, confirmed_at=now)

        match_row = compliance_repo.get_by_id(match_id)
        # 获取 project_id 并传播失效
        req = self.repo.get_by_id(match_row["requirement_item_id"])
        self._propagate_comparison_dirty(req["project_id"])
        return match_row

    def accept_match(self, match_id: str, is_acceptable: bool) -> dict:
        """标记部分符合为可接受"""
        from db.compliance_repo import ComplianceRepo
        compliance_repo = ComplianceRepo(self.db)
        compliance_repo.update_acceptable(match_id, is_acceptable)

        match_row = compliance_repo.get_by_id(match_id)
        req = self.repo.get_by_id(match_row["requirement_item_id"])
        self._propagate_comparison_dirty(req["project_id"])
        return match_row

    # ---- 供资格判定 ----

    def get_eligible_supplier_ids(self, group_id: str) -> list[str]:
        from db.compliance_repo import ComplianceRepo
        return ComplianceRepo(self.db).get_eligible_supplier_ids(group_id)

    # ---- 私有方法（新增） ----

    def _get_confirmed_groups(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM commodity_groups
                   WHERE project_id = ? AND status IN ('confirmed', 'candidate')""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_supplier_rows_for_group(self, group_id: str) -> dict[str, list[dict]]:
        """返回 {supplier_file_id: [standardized_row, ...]}"""
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sf.id as supplier_file_id, sf.supplier_name
                   FROM group_members gm
                   JOIN standardized_rows sr ON sr.id = gm.standardized_row_id
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE gm.group_id = ?""",
                (group_id,),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        result: dict[str, list[dict]] = {}
        for row in rows:
            sid = row["supplier_file_id"]
            result.setdefault(sid, []).append(row)
        return result

    def _get_supplier_names(self, project_id: str) -> dict[str, str]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT id, supplier_name FROM supplier_files WHERE project_id = ?",
                (project_id,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def _propagate_comparison_dirty(self, project_id: str) -> None:
        """符合性结果变更 → comparison dirty"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET comparison_status = 'dirty', updated_at = ? WHERE id = ?",
                (now, project_id),
            )

    def _update_stage_status(self, project_id: str, stage: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {stage} = ?, updated_at = ? WHERE id = ?",
                (status, now, project_id),
            )
```

## 测试与验收

### tests/test_compliance_evaluator.py

```python
import pytest
from engines.compliance_evaluator import ComplianceEvaluator


class TestComplianceEvaluator:
    def setup_method(self):
        self.engine = ComplianceEvaluator()

    def test_keyword_match_found(self):
        req = {"match_type": "keyword", "expected_value": "DDR5"}
        rows = [{"product_name": "ThinkPad E14", "spec_model": "DDR5 16GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "match"
        assert result.needs_review is False

    def test_keyword_match_not_found(self):
        req = {"match_type": "keyword", "expected_value": "DDR5"}
        rows = [{"product_name": "ThinkPad E14", "spec_model": "DDR4 8GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
        assert result.needs_review is True

    def test_keyword_case_insensitive(self):
        req = {"match_type": "keyword", "expected_value": "ssd"}
        rows = [{"product_name": "笔记本", "spec_model": "512GB SSD", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "match"

    def test_numeric_match_gte_pass(self):
        req = {"match_type": "numeric", "expected_value": "16", "operator": "gte"}
        rows = [{"product_name": "笔记本", "spec_model": "内存32GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "match"

    def test_numeric_match_gte_fail(self):
        req = {"match_type": "numeric", "expected_value": "16", "operator": "gte"}
        rows = [{"product_name": "笔记本", "spec_model": "内存8GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "no_match"

    def test_numeric_no_number_found(self):
        req = {"match_type": "numeric", "expected_value": "16", "operator": "gte"}
        rows = [{"product_name": "笔记本", "spec_model": "大容量内存", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
        assert result.needs_review is True

    def test_manual_always_unclear(self):
        req = {"match_type": "manual", "expected_value": "需人工判断"}
        rows = [{"product_name": "test", "spec_model": "test", "remark": "test"}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
        assert result.needs_review is True

    def test_keyword_empty_expected_value(self):
        req = {"match_type": "keyword", "expected_value": ""}
        rows = [{"product_name": "test", "spec_model": "test", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
```

### tests/test_compliance_repo.py

```python
import pytest
import uuid


class TestComplianceRepo:
    def test_insert_and_get(self, project_db):
        from db.compliance_repo import ComplianceRepo
        repo = ComplianceRepo(project_db)
        mid = str(uuid.uuid4())
        repo.insert(
            match_id=mid, requirement_item_id="r1",
            commodity_group_id="g1", supplier_file_id="sf1",
            status="match", is_acceptable=False, match_score=1.0,
            evidence_text="找到关键词", evidence_location="{}",
            match_method="keyword", needs_review=False, engine_versions="{}",
        )
        row = repo.get_by_id(mid)
        assert row is not None
        assert row["status"] == "match"

    def test_update_status(self, project_db):
        from db.compliance_repo import ComplianceRepo
        repo = ComplianceRepo(project_db)
        mid = str(uuid.uuid4())
        repo.insert(
            match_id=mid, requirement_item_id="r1",
            commodity_group_id="g1", supplier_file_id="sf1",
            status="unclear", is_acceptable=False, match_score=0.0,
            evidence_text="", evidence_location="{}",
            match_method="manual", needs_review=True, engine_versions="{}",
        )
        repo.update_status(mid, "match", confirmed_at="2026-01-01T00:00:00Z")
        row = repo.get_by_id(mid)
        assert row["status"] == "match"
        assert row["needs_review"] == 0

    def test_update_acceptable(self, project_db):
        from db.compliance_repo import ComplianceRepo
        repo = ComplianceRepo(project_db)
        mid = str(uuid.uuid4())
        repo.insert(
            match_id=mid, requirement_item_id="r1",
            commodity_group_id="g1", supplier_file_id="sf1",
            status="partial", is_acceptable=False, match_score=0.5,
            evidence_text="", evidence_location="{}",
            match_method="keyword", needs_review=True, engine_versions="{}",
        )
        repo.update_acceptable(mid, True)
        row = repo.get_by_id(mid)
        assert row["is_acceptable"] == 1
```

### 门禁命令

```bash
cd backend
ruff check engines/compliance_evaluator.py db/compliance_repo.py services/compliance_service.py
mypy engines/compliance_evaluator.py db/compliance_repo.py services/compliance_service.py --ignore-missing-imports
pytest tests/test_compliance_evaluator.py tests/test_compliance_repo.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| keyword 命中 → status == "match" | needs_review == False |
| keyword 未命中 → status == "unclear" | needs_review == True |
| keyword 大小写不敏感 | status == "match" |
| numeric gte 满足 → "match" | match_score == 1.0 |
| numeric gte 不满足 → "no_match" | match_score == 0.0 |
| numeric 无数值 → "unclear" | needs_review == True |
| manual → "unclear" + needs_review | 固定行为 |
| 插入匹配结果 → 可查询 | status 正确 |
| 更新 status → needs_review 清零 | confirmed_at 有值 |
| 更新 is_acceptable → 生效 | is_acceptable == 1 |

## 提交

```bash
git add backend/engines/compliance_evaluator.py backend/db/compliance_repo.py \
       backend/services/compliance_service.py \
       backend/tests/test_compliance_evaluator.py backend/tests/test_compliance_repo.py
git commit -m "Phase 4.2: 符合性匹配引擎 — keyword/numeric/manual 三类匹配 + ComplianceRepo + 矩阵/确认/可接受"
```
