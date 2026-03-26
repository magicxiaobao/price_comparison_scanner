# Task 4.4: PriceComparator — 比价计算 + 异常检测 + 双口径最低价

## 输入条件

- Phase 3 完成（归组数据可用）
- Task 4.11 完成（comparison Pydantic 模型已定义）
- 数据库 `comparison_results` 表结构已就绪（Phase 0 建表）

## 输出物

- 创建: `backend/engines/price_comparator.py`
- 创建: `backend/db/comparison_repo.py`
- 创建: `backend/services/comparison_service.py`
- 创建: `backend/tests/test_price_comparator.py`
- 创建: `backend/tests/test_comparison_repo.py`

## 禁止修改

- 不修改 `backend/db/schema.sql`
- 不修改 `backend/models/comparison.py`（已稳定）
- 不修改已有引擎文件
- 不修改 `frontend/`

## 实现规格

### engines/price_comparator.py

```python
import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SupplierPriceData:
    """供应商报价数据"""
    supplier_file_id: str
    supplier_name: str
    unit_price: Optional[float]
    total_price: Optional[float]
    tax_basis: Optional[str]    # 含税 / 不含税 / 未知
    unit: Optional[str]
    currency: Optional[str]     # CNY 等


@dataclass
class AnomalyInfo:
    """异常信息"""
    type: str                    # tax_basis_mismatch / unit_mismatch / currency_mismatch / missing_required_field
    description: str
    blocking: bool
    affected_suppliers: list[str]


@dataclass
class ComparisonData:
    """单个商品组的比价结果"""
    group_id: str
    group_name: str
    comparison_status: str       # comparable / blocked / partial
    supplier_prices: list[SupplierPriceData]
    min_price: Optional[float]
    effective_min_price: Optional[float]
    max_price: Optional[float]
    avg_price: Optional[float]
    price_diff: Optional[float]
    has_anomaly: bool
    anomaly_details: list[AnomalyInfo]
    missing_suppliers: list[str]


class PriceComparator:
    """比价引擎 — 比价计算 + 异常检测 + 双口径最低价"""

    ENGINE_VERSION = "price_comparator:1.0"

    def compare_group(
        self,
        group: dict,
        supplier_rows_map: dict[str, list[dict]],
        eligible_supplier_ids: Optional[list[str]] = None,
    ) -> ComparisonData:
        """
        对单个商品组计算比价结果。

        group: commodity_groups 表记录
        supplier_rows_map: {supplier_file_id: [standardized_row, ...]}
        eligible_supplier_ids: 有资格参与有效最低价的供应商 ID 列表（来自 ComplianceEvaluator）
                               None — 跳过符合性模块（无需求标准），effective_min_price = min_price
                               [] — 有需求标准但无任何供应商满足全部必选项，effective_min_price = None
        """
        # 1. 收集各供应商报价
        prices: list[SupplierPriceData] = []
        for sid, rows in supplier_rows_map.items():
            supplier_name = rows[0].get("supplier_name", "") if rows else ""
            # 取该供应商在该组下的代表行（通常一行，多行时取第一行）
            row = rows[0] if rows else {}
            prices.append(SupplierPriceData(
                supplier_file_id=sid,
                supplier_name=supplier_name,
                unit_price=self._safe_float(row.get("unit_price")),
                total_price=self._safe_float(row.get("total_price")),
                tax_basis=row.get("tax_basis"),
                unit=row.get("unit"),
                currency=row.get("currency", "CNY"),
            ))

        # 2. 检测异常
        anomalies = self.detect_anomalies(prices)
        has_anomaly = len(anomalies) > 0
        has_blocking = any(a.blocking for a in anomalies)

        # 3. 计算全量最低价
        valid_prices = [p.unit_price for p in prices if p.unit_price is not None]
        min_price = min(valid_prices) if valid_prices else None
        max_price = max(valid_prices) if valid_prices else None
        avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else None
        price_diff = (max_price - min_price) if min_price is not None and max_price is not None else None

        # 4. 计算有效最低价
        if eligible_supplier_ids is None:
            # None: 跳过符合性 → 有效最低价 = 全量最低价
            effective_min_price = min_price
        elif len(eligible_supplier_ids) == 0:
            # []: 有需求标准但无合格供应商 → 无有效最低价
            effective_min_price = None
        else:
            eligible_prices = [
                p.unit_price for p in prices
                if p.unit_price is not None and p.supplier_file_id in eligible_supplier_ids
            ]
            effective_min_price = min(eligible_prices) if eligible_prices else None

        # 5. 确定比较状态
        if has_blocking:
            comparison_status = "blocked"
        elif has_anomaly:
            comparison_status = "partial"
        else:
            comparison_status = "comparable"

        # 6. 检测缺项供应商
        missing = self._detect_missing_suppliers(prices)

        return ComparisonData(
            group_id=group["id"],
            group_name=group.get("group_name", ""),
            comparison_status=comparison_status,
            supplier_prices=prices,
            min_price=min_price,
            effective_min_price=effective_min_price,
            max_price=max_price,
            avg_price=avg_price,
            price_diff=price_diff,
            has_anomaly=has_anomaly,
            anomaly_details=anomalies,
            missing_suppliers=missing,
        )

    def detect_anomalies(self, prices: list[SupplierPriceData]) -> list[AnomalyInfo]:
        """
        异常检测（PRD 5.8）。

        - 税价口径不一致 → 阻断该组最低价结论
        - 单位不一致 → 阻断该组价格比较
        - 币种不一致 → 阻断涉及组的价格比较
        - 必填字段缺失 → 标记不阻断
        """
        anomalies: list[AnomalyInfo] = []

        # 税价口径不一致
        tax_bases = set()
        for p in prices:
            if p.tax_basis and p.tax_basis != "未知":
                tax_bases.add(p.tax_basis)
        if len(tax_bases) > 1:
            anomalies.append(AnomalyInfo(
                type="tax_basis_mismatch",
                description=f"税价口径不一致：{', '.join(tax_bases)}",
                blocking=True,
                affected_suppliers=[p.supplier_name for p in prices],
            ))

        # 单位不一致
        units = set()
        for p in prices:
            if p.unit:
                units.add(p.unit.strip().lower())
        if len(units) > 1:
            anomalies.append(AnomalyInfo(
                type="unit_mismatch",
                description=f"单位不一致：{', '.join(units)}",
                blocking=True,
                affected_suppliers=[p.supplier_name for p in prices],
            ))

        # 币种不一致
        currencies = set()
        for p in prices:
            if p.currency:
                currencies.add(p.currency.upper())
        if len(currencies) > 1:
            anomalies.append(AnomalyInfo(
                type="currency_mismatch",
                description=f"币种不一致：{', '.join(currencies)}",
                blocking=True,
                affected_suppliers=[p.supplier_name for p in prices],
            ))

        # 必填字段缺失
        for p in prices:
            missing_fields: list[str] = []
            if p.unit_price is None:
                missing_fields.append("单价")
            if not p.unit:
                missing_fields.append("单位")
            if missing_fields:
                anomalies.append(AnomalyInfo(
                    type="missing_required_field",
                    description=f"{p.supplier_name} 缺失: {', '.join(missing_fields)}",
                    blocking=False,
                    affected_suppliers=[p.supplier_name],
                ))

        return anomalies

    def _detect_missing_suppliers(self, prices: list[SupplierPriceData]) -> list[str]:
        """检测无报价的供应商"""
        return [p.supplier_name for p in prices if p.unit_price is None]

    def _safe_float(self, value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
```

### db/comparison_repo.py

```python
from db.database import Database
from typing import Optional
from datetime import datetime, timezone


class ComparisonRepo:
    """comparison_results 表操作 — 纯数据访问层"""

    def __init__(self, db: Database):
        self.db = db

    def insert(
        self,
        result_id: str,
        group_id: str,
        project_id: str,
        engine_versions: str,
        comparison_status: str,
        supplier_prices: str,      # JSON
        min_price: Optional[float],
        effective_min_price: Optional[float],
        max_price: Optional[float],
        avg_price: Optional[float],
        price_diff: Optional[float],
        has_anomaly: bool,
        anomaly_details: str,      # JSON
        missing_suppliers: str,    # JSON
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO comparison_results
                   (id, group_id, project_id, engine_versions, comparison_status,
                    supplier_prices, min_price, effective_min_price, max_price, avg_price,
                    price_diff, has_anomaly, anomaly_details, missing_suppliers, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result_id, group_id, project_id, engine_versions, comparison_status,
                 supplier_prices, min_price, effective_min_price, max_price, avg_price,
                 price_diff, 1 if has_anomaly else 0, anomaly_details, missing_suppliers, now),
            )
        return self.get_by_id(result_id)

    def get_by_id(self, result_id: str) -> Optional[dict]:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM comparison_results WHERE id = ?", (result_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_by_project(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT * FROM comparison_results WHERE project_id = ? ORDER BY generated_at DESC",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_by_project(self, project_id: str) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM comparison_results WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount
```

### services/comparison_service.py

```python
import json
import uuid
from datetime import datetime, timezone
from db.database import Database
from db.comparison_repo import ComparisonRepo
from engines.price_comparator import PriceComparator
from models.comparison import ComparisonResultResponse, SupplierPrice, AnomalyDetail


class ComparisonService:
    """比价业务编排"""

    def __init__(self, db: Database):
        self.db = db
        self.repo = ComparisonRepo(db)
        self.engine = PriceComparator()

    def generate_comparison(self, project_id: str) -> list[ComparisonResultResponse]:
        """
        生成比价结果。

        1. 清除旧结果
        2. 获取已确认归组
        3. 检查是否有需求标准（决定是否传入 eligible_supplier_ids）
        4. 对每个组调用 PriceComparator
        5. 持久化
        6. 更新阶段状态
        """
        self.repo.delete_by_project(project_id)

        groups = self._get_confirmed_groups(project_id)
        has_requirements = self._has_requirements(project_id)

        results: list[ComparisonResultResponse] = []
        for group in groups:
            supplier_rows_map = self._get_supplier_rows_for_group(group["id"])

            eligible_ids = None
            if has_requirements:
                eligible_ids = self._get_eligible_supplier_ids(group["id"])

            comparison = self.engine.compare_group(group, supplier_rows_map, eligible_ids)

            result_id = str(uuid.uuid4())
            supplier_prices_json = json.dumps([
                {
                    "supplier_file_id": p.supplier_file_id,
                    "supplier_name": p.supplier_name,
                    "unit_price": p.unit_price,
                    "total_price": p.total_price,
                }
                for p in comparison.supplier_prices
            ], ensure_ascii=False)

            anomaly_json = json.dumps([
                {
                    "type": a.type,
                    "description": a.description,
                    "blocking": a.blocking,
                    "affected_suppliers": a.affected_suppliers,
                }
                for a in comparison.anomaly_details
            ], ensure_ascii=False)

            missing_json = json.dumps(comparison.missing_suppliers, ensure_ascii=False)

            self.repo.insert(
                result_id=result_id,
                group_id=group["id"],
                project_id=project_id,
                engine_versions=json.dumps({"comparator": self.engine.ENGINE_VERSION}),
                comparison_status=comparison.comparison_status,
                supplier_prices=supplier_prices_json,
                min_price=comparison.min_price,
                effective_min_price=comparison.effective_min_price,
                max_price=comparison.max_price,
                avg_price=comparison.avg_price,
                price_diff=comparison.price_diff,
                has_anomaly=comparison.has_anomaly,
                anomaly_details=anomaly_json,
                missing_suppliers=missing_json,
            )

            results.append(self._to_response(self.repo.get_by_id(result_id), group))

        self._update_stage_status(project_id, "comparison_status", "completed")
        return results

    def list_results(self, project_id: str) -> list[ComparisonResultResponse]:
        rows = self.repo.list_by_project(project_id)
        results = []
        for row in rows:
            group = self._get_group(row["group_id"])
            if group:
                results.append(self._to_response(row, group))
        return results

    # ---- 私有方法 ----

    def _get_confirmed_groups(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT * FROM commodity_groups
                   WHERE project_id = ? AND status IN ('confirmed', 'candidate')""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_group(self, group_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM commodity_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def _get_supplier_rows_for_group(self, group_id: str) -> dict[str, list[dict]]:
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

    def _has_requirements(self, project_id: str) -> bool:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return cursor.fetchone()[0] > 0

    def _get_eligible_supplier_ids(self, group_id: str) -> list[str]:
        from db.compliance_repo import ComplianceRepo
        return ComplianceRepo(self.db).get_eligible_supplier_ids(group_id)

    def _update_stage_status(self, project_id: str, stage: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {stage} = ?, updated_at = ? WHERE id = ?",
                (status, now, project_id),
            )

    def _to_response(self, row: dict, group: dict) -> ComparisonResultResponse:
        supplier_prices = json.loads(row.get("supplier_prices", "[]"))
        anomaly_details = json.loads(row.get("anomaly_details", "[]"))
        missing = json.loads(row.get("missing_suppliers", "[]"))

        return ComparisonResultResponse(
            id=row["id"],
            group_id=row["group_id"],
            group_name=group.get("group_name", ""),
            project_id=row["project_id"],
            comparison_status=row["comparison_status"],
            supplier_prices=[SupplierPrice(**sp) for sp in supplier_prices],
            min_price=row.get("min_price"),
            effective_min_price=row.get("effective_min_price"),
            max_price=row.get("max_price"),
            avg_price=row.get("avg_price"),
            price_diff=row.get("price_diff"),
            has_anomaly=bool(row.get("has_anomaly", 0)),
            anomaly_details=[AnomalyDetail(**ad) for ad in anomaly_details],
            missing_suppliers=missing,
            generated_at=row["generated_at"],
        )
```

## 测试与验收

### tests/test_price_comparator.py

```python
import pytest
from engines.price_comparator import PriceComparator, SupplierPriceData


class TestPriceComparator:
    def setup_method(self):
        self.engine = PriceComparator()

    def test_basic_comparison(self):
        group = {"id": "g1", "group_name": "ThinkPad E14"}
        rows = {
            "sf1": [{"supplier_name": "联想", "unit_price": 4299, "total_price": 42990, "tax_basis": "含税", "unit": "台", "currency": "CNY"}],
            "sf2": [{"supplier_name": "戴尔", "unit_price": 4599, "total_price": 45990, "tax_basis": "含税", "unit": "台", "currency": "CNY"}],
            "sf3": [{"supplier_name": "惠普", "unit_price": 4199, "total_price": 41990, "tax_basis": "含税", "unit": "台", "currency": "CNY"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.min_price == 4199
        assert result.max_price == 4599
        assert result.effective_min_price == 4199  # 无需求标准
        assert result.comparison_status == "comparable"
        assert result.has_anomaly is False

    def test_effective_min_with_eligible(self):
        group = {"id": "g1", "group_name": "ThinkPad E14"}
        rows = {
            "sf1": [{"supplier_name": "联想", "unit_price": 4299, "unit": "台", "currency": "CNY"}],
            "sf2": [{"supplier_name": "戴尔", "unit_price": 4599, "unit": "台", "currency": "CNY"}],
            "sf3": [{"supplier_name": "惠普", "unit_price": 4199, "unit": "台", "currency": "CNY"}],
        }
        # 惠普不符合需求，仅联想和戴尔参与有效最低价
        result = self.engine.compare_group(group, rows, eligible_supplier_ids=["sf1", "sf2"])
        assert result.min_price == 4199         # 全量最低价
        assert result.effective_min_price == 4299  # 有效最低价

    def test_tax_basis_mismatch(self):
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "tax_basis": "含税", "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "tax_basis": "不含税", "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.has_anomaly is True
        assert result.comparison_status == "blocked"
        assert any(a.type == "tax_basis_mismatch" for a in result.anomaly_details)

    def test_unit_mismatch(self):
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "unit": "套"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.comparison_status == "blocked"
        assert any(a.type == "unit_mismatch" for a in result.anomaly_details)

    def test_currency_mismatch(self):
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台", "currency": "CNY"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "unit": "台", "currency": "USD"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.comparison_status == "blocked"
        assert any(a.type == "currency_mismatch" for a in result.anomaly_details)

    def test_missing_required_field(self):
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": None, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert any(a.type == "missing_required_field" for a in result.anomaly_details)
        # 必填缺失不阻断
        assert not any(a.blocking and a.type == "missing_required_field" for a in result.anomaly_details)

    def test_no_eligible_suppliers(self):
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows, eligible_supplier_ids=[])
        assert result.effective_min_price is None

    def test_missing_suppliers_detected(self):
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": None, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert "B" in result.missing_suppliers
```

### tests/test_comparison_repo.py

```python
import pytest
import uuid
import json


class TestComparisonRepo:
    def test_insert_and_get(self, project_db):
        from db.comparison_repo import ComparisonRepo
        repo = ComparisonRepo(project_db)
        rid = str(uuid.uuid4())
        repo.insert(
            result_id=rid, group_id="g1", project_id="p1",
            engine_versions='{}', comparison_status="comparable",
            supplier_prices='[]', min_price=100.0,
            effective_min_price=100.0, max_price=200.0,
            avg_price=150.0, price_diff=100.0,
            has_anomaly=False, anomaly_details='[]', missing_suppliers='[]',
        )
        row = repo.get_by_id(rid)
        assert row is not None
        assert row["min_price"] == 100.0
        assert row["comparison_status"] == "comparable"

    def test_list_by_project(self, project_db):
        from db.comparison_repo import ComparisonRepo
        repo = ComparisonRepo(project_db)
        for _ in range(3):
            repo.insert(
                result_id=str(uuid.uuid4()), group_id="g1", project_id="p1",
                engine_versions='{}', comparison_status="comparable",
                supplier_prices='[]', min_price=100.0,
                effective_min_price=100.0, max_price=200.0,
                avg_price=150.0, price_diff=100.0,
                has_anomaly=False, anomaly_details='[]', missing_suppliers='[]',
            )
        rows = repo.list_by_project("p1")
        assert len(rows) == 3

    def test_delete_by_project(self, project_db):
        from db.comparison_repo import ComparisonRepo
        repo = ComparisonRepo(project_db)
        repo.insert(
            result_id=str(uuid.uuid4()), group_id="g1", project_id="p1",
            engine_versions='{}', comparison_status="comparable",
            supplier_prices='[]', min_price=100.0,
            effective_min_price=100.0, max_price=200.0,
            avg_price=150.0, price_diff=100.0,
            has_anomaly=False, anomaly_details='[]', missing_suppliers='[]',
        )
        count = repo.delete_by_project("p1")
        assert count == 1
        assert repo.list_by_project("p1") == []
```

### 门禁命令

```bash
cd backend
ruff check engines/price_comparator.py db/comparison_repo.py services/comparison_service.py
mypy engines/price_comparator.py db/comparison_repo.py services/comparison_service.py --ignore-missing-imports
pytest tests/test_price_comparator.py tests/test_comparison_repo.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| 3 供应商正常比价 → min/max/avg 正确 | comparable |
| 有效最低价仅含 eligible 供应商 | effective_min != min |
| 税价口径不一致 → blocked | anomaly type 正确 |
| 单位不一致 → blocked | anomaly type 正确 |
| 币种不一致 → blocked | anomaly type 正确 |
| 必填缺失 → 标记不阻断 | blocking == False |
| 无 eligible 供应商 → effective_min_price None | 正确 |
| 缺项供应商被检出 | missing_suppliers 包含名称 |
| Repo 插入/查询/删除 | 功能正确 |

## 提交

```bash
git add backend/engines/price_comparator.py backend/db/comparison_repo.py \
       backend/services/comparison_service.py \
       backend/tests/test_price_comparator.py backend/tests/test_comparison_repo.py
git commit -m "Phase 4.4: PriceComparator — 比价计算 + 异常检测(税价/单位/币种/缺项) + 双口径最低价 + ComparisonRepo"
```
