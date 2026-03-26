# Task 2.4: TableStandardizer — 字段映射 + 值标准化

## 输入条件

- Task 2.2 完成（`engines/rule_engine.py` 就绪）
- Task 2.6 完成（`models/standardization.py` 中标准化相关模型就绪）
- Phase 1 完成（`raw_tables` 表有数据可用）

## 输出物

- 创建: `backend/engines/table_standardizer.py`
- 创建: `backend/tests/test_table_standardizer.py`

## 禁止修改

- 不修改 `engines/rule_engine.py`（已稳定）
- 不修改 `db/schema.sql`
- 不修改 `api/` 目录（API 在 Task 2.5 实现）
- 不修改 `frontend/`

## 实现规格

### engines/table_standardizer.py

```python
import uuid
from models.rule import RuleSet, ColumnMappingRule, MatchResult
from models.standardization import (
    StandardizedRowCreate, SourceLocationItem, SourceLocation, HitRuleSnapshot,
)
from engines.rule_engine import RuleEngine

# 9 个标准字段
STANDARD_FIELDS = [
    "product_name", "spec_model", "unit", "quantity",
    "unit_price", "total_price", "tax_rate",
    "delivery_period", "remark",
]

# 数值型标准字段
NUMERIC_FIELDS = {"quantity", "unit_price", "total_price"}

# 必填字段（缺失时 needs_review=True）
REQUIRED_FIELDS = {"product_name", "unit", "quantity", "unit_price"}

# 税价口径识别关键词
TAX_INCLUSIVE_KEYWORDS = ["含税单价", "含税价", "含税"]
TAX_EXCLUSIVE_KEYWORDS = ["不含税单价", "未税单价", "不含税", "未税"]

class TableStandardizer:
    """
    接收 RawTable 数据 + RuleSet → 输出 StandardizedRow 列表。
    职责：
    1. 列名映射（通过 RuleEngine 匹配）
    2. 值标准化（数值解析、空白清理、值替换规则）
    3. 总价自动计算（quantity × unit_price，原表未提供时）
    4. 税价口径识别（有限枚举场景自动，其余 unknown）
    5. source_location 字段级追溯
    6. 规则命中快照记录
    7. 置信度标记
    """

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    def standardize(
        self,
        raw_table_id: str,
        supplier_file_id: str,
        headers: list[str],
        rows: list[list],
        file_type: str,            # xlsx / docx / pdf
        sheet_name: str | None = None,
        page_number: int | None = None,
        table_index: int = 0,
        rules: RuleSet | None = None,
        project_rules: RuleSet | None = None,
    ) -> list[StandardizedRowCreate]:
        """
        标准化入口。
        返回 StandardizedRowCreate 列表。
        """
        if rules is None:
            rules = self.rule_engine.load_global_rules()

        # 1. 列名映射
        column_mapping, hit_snapshots, mapping_issues = self._map_columns(
            headers, rules, project_rules
        )

        # 2. 逐行标准化
        result = []
        for row_idx, row_data in enumerate(rows):
            std_row = self._standardize_row(
                raw_table_id=raw_table_id,
                supplier_file_id=supplier_file_id,
                row_index=row_idx,
                headers=headers,
                row_data=row_data,
                column_mapping=column_mapping,
                hit_snapshots=hit_snapshots,
                file_type=file_type,
                sheet_name=sheet_name,
                page_number=page_number,
                table_index=table_index,
                rules=rules,
            )
            result.append(std_row)

        return result

    def _map_columns(
        self,
        headers: list[str],
        rules: RuleSet,
        project_rules: RuleSet | None,
    ) -> tuple[dict[str, str], list[HitRuleSnapshot], list[dict]]:
        """
        列名映射。
        返回：
        - column_mapping: {原始列名: 标准字段名}
        - hit_snapshots: 命中的规则快照列表
        - issues: 未映射列 / 冲突列
        """
        column_mapping: dict[str, str] = {}
        hit_snapshots: list[HitRuleSnapshot] = []
        issues: list[dict] = []

        for header in headers:
            match_result = self.rule_engine.match_column(header, rules, project_rules)
            if match_result.matched and match_result.target_field:
                column_mapping[header] = match_result.target_field
                if match_result.matched_rule:
                    hit_snapshots.append(HitRuleSnapshot(
                        rule_id=match_result.matched_rule.id,
                        rule_name=f"{header}→{match_result.target_field}",
                        match_content=f"{header}→{match_result.target_field}",
                        match_mode=match_result.matched_rule.match_mode.value,
                    ))
            else:
                issues.append({"header": header, "type": "unmapped"})

            if match_result.conflicts:
                issues.append({
                    "header": header,
                    "type": "conflict",
                    "conflicts": [r.id for r in match_result.conflicts],
                })

        return column_mapping, hit_snapshots, issues

    def _standardize_row(
        self,
        raw_table_id: str,
        supplier_file_id: str,
        row_index: int,
        headers: list[str],
        row_data: list,
        column_mapping: dict[str, str],
        hit_snapshots: list[HitRuleSnapshot],
        file_type: str,
        sheet_name: str | None,
        page_number: int | None,
        table_index: int,
        rules: RuleSet,
    ) -> StandardizedRowCreate:
        """标准化单行数据"""
        # 提取标准字段值
        field_values: dict[str, object] = {}
        source_location: SourceLocation = {}

        for col_idx, header in enumerate(headers):
            if header not in column_mapping:
                continue
            target_field = column_mapping[header]
            raw_value = row_data[col_idx] if col_idx < len(row_data) else None

            # 值标准化
            field_values[target_field] = self._normalize_value(target_field, raw_value, rules)

            # 来源定位
            source_location[target_field] = self._build_source_location(
                file_type, sheet_name, page_number, table_index, row_index, col_idx
            )

        # 总价自动计算
        if "total_price" not in field_values or field_values.get("total_price") is None:
            qty = field_values.get("quantity")
            price = field_values.get("unit_price")
            if qty is not None and price is not None:
                try:
                    field_values["total_price"] = float(qty) * float(price)
                except (ValueError, TypeError):
                    pass

        # 税价口径识别
        tax_basis = self._detect_tax_basis(headers, column_mapping)

        # 置信度和审核标记
        confidence = 1.0
        needs_review = False
        for req_field in REQUIRED_FIELDS:
            if field_values.get(req_field) is None:
                needs_review = True
                confidence = min(confidence, 0.5)
                break

        return StandardizedRowCreate(
            id=str(uuid.uuid4()),
            raw_table_id=raw_table_id,
            supplier_file_id=supplier_file_id,
            row_index=row_index,
            product_name=field_values.get("product_name"),
            spec_model=field_values.get("spec_model"),
            unit=field_values.get("unit"),
            quantity=self._to_float(field_values.get("quantity")),
            unit_price=self._to_float(field_values.get("unit_price")),
            total_price=self._to_float(field_values.get("total_price")),
            tax_rate=str(field_values["tax_rate"]) if field_values.get("tax_rate") is not None else None,
            delivery_period=str(field_values["delivery_period"]) if field_values.get("delivery_period") is not None else None,
            remark=str(field_values["remark"]) if field_values.get("remark") is not None else None,
            source_location=source_location,
            column_mapping=column_mapping,
            hit_rule_snapshots=hit_snapshots,
            confidence=confidence,
            needs_review=needs_review,
            tax_basis=tax_basis,
        )

    def _normalize_value(self, field: str, raw_value: object, rules: RuleSet) -> object:
        """
        值标准化：
        - 数值字段：解析数字（去除逗号、货币符号、空格）
        - 文本字段：strip + 值替换规则
        """
        ...

    def _detect_tax_basis(self, headers: list[str], column_mapping: dict[str, str]) -> str:
        """
        税价口径识别（PRD 5.3 有限枚举场景）：
        - 列名包含含税关键词 → known_inclusive
        - 列名包含不含税关键词 → known_exclusive
        - 其余 → unknown
        """
        for header, target in column_mapping.items():
            if target == "unit_price":
                header_lower = header.lower().strip()
                if any(kw in header_lower for kw in TAX_INCLUSIVE_KEYWORDS):
                    return "known_inclusive"
                if any(kw in header_lower for kw in TAX_EXCLUSIVE_KEYWORDS):
                    return "known_exclusive"
        return "unknown"

    def _build_source_location(
        self, file_type: str, sheet_name: str | None,
        page_number: int | None, table_index: int,
        row_index: int, col_index: int,
    ) -> SourceLocationItem:
        """构建字段来源定位"""
        if file_type == "xlsx":
            return SourceLocationItem(
                type="xlsx",
                sheet=sheet_name,
                cell=self._index_to_cell(row_index, col_index),
            )
        elif file_type == "docx":
            return SourceLocationItem(
                type="docx",
                table_index=table_index,
                row=row_index,
                col=col_index,
            )
        else:  # pdf
            return SourceLocationItem(
                type="pdf",
                page=page_number,
                table_index=table_index,
                row=row_index,
                col=col_index,
                extraction_mode="structure",
            )

    @staticmethod
    def _index_to_cell(row: int, col: int) -> str:
        """将行列索引转为 Excel 单元格引用（如 A1, B3）"""
        col_letter = ""
        c = col
        while c >= 0:
            col_letter = chr(65 + c % 26) + col_letter
            c = c // 26 - 1
        return f"{col_letter}{row + 1}"

    @staticmethod
    def _to_float(value: object) -> float | None:
        """安全转 float"""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")
            return float(value)
        except (ValueError, TypeError):
            return None
```

**关键设计点：**

1. **纯引擎**：`TableStandardizer` 不依赖 FastAPI、不直接操作数据库。接收原始数据，输出 `StandardizedRowCreate` 列表
2. **列名映射**：委托 `RuleEngine.match_column()` 完成
3. **总价自动计算**：`quantity × unit_price`，仅在原表未提供 `total_price` 时计算
4. **税价口径识别**：仅在列名明确包含含税/不含税关键词时自动识别，其余标记 `unknown`
5. **source_location**：字段级追溯，每个标准字段独立记录原始来源位置
6. **规则命中快照**：记录命中的规则 ID、名称、匹配内容和匹配方式
7. **值标准化**：数值字段去除逗号/货币符号后解析；文本字段 strip + 值替换规则
8. **置信度**：必填字段缺失时降低到 0.5 并标记 `needs_review`

## 测试与验收

### fixture 设计

```python
@pytest.fixture
def rule_engine(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    engine = RuleEngine(rules_dir)
    engine.reset_default()
    return engine

@pytest.fixture
def standardizer(rule_engine):
    return TableStandardizer(rule_engine)
```

### 测试用例清单

```python
# ---- 列名映射 ----
# test_map_columns_basic — 基本列名映射正确
# test_map_columns_unmapped — 未映射列标记为 issue
# test_map_columns_conflict — 冲突列记录到 issues

# ---- 值标准化 ----
# test_normalize_numeric_with_comma — "1,234.56" → 1234.56
# test_normalize_numeric_with_currency — "¥4,299" → 4299.0
# test_normalize_text_strip — 前后空格去除

# ---- 总价计算 ----
# test_total_price_auto_calc — 原表无总价时自动计算 qty × price
# test_total_price_from_original — 原表有总价时保留原值

# ---- 税价口径 ----
# test_tax_basis_inclusive — 列名"含税单价" → known_inclusive
# test_tax_basis_exclusive — 列名"不含税单价" → known_exclusive
# test_tax_basis_unknown — 列名"单价" → unknown

# ---- source_location ----
# test_source_location_xlsx — Excel 来源正确
# test_source_location_docx — Word 来源正确
# test_source_location_pdf — PDF 来源正确

# ---- 完整标准化 ----
# test_standardize_basic — 基本标准化流程
# test_standardize_missing_required — 必填字段缺失 → needs_review=True, confidence=0.5
# test_standardize_multiple_rows — 多行标准化

# ---- 辅助方法 ----
# test_index_to_cell — (0,0)→"A1", (2,3)→"D3", (0,26)→"AA1"
# test_to_float — 各种格式数值解析
```

**断言清单：**

- 列名映射后 `column_mapping` 中的标准字段在 `STANDARD_FIELDS` 白名单中
- 数值解析正确（含逗号、货币符号、空格等情况）
- 总价自动计算 `quantity * unit_price` 精度正确
- 税价口径识别符合 PRD 5.3 规则
- `source_location` 每个字段独立记录来源
- `hit_rule_snapshots` 包含命中规则的 ID 和匹配方式
- 必填字段缺失时 `needs_review=True`，`confidence <= 0.5`
- `StandardizedRowCreate.id` 为有效 UUID

**门禁命令：**

```bash
cd backend
ruff check engines/table_standardizer.py tests/test_table_standardizer.py
mypy engines/table_standardizer.py --ignore-missing-imports
pytest tests/test_table_standardizer.py -x -q
```

## 提交

```bash
git add backend/engines/table_standardizer.py backend/tests/test_table_standardizer.py
git commit -m "Phase 2.4: TableStandardizer — 列名映射 + 值标准化 + 总价计算 + 税价口径 + 追溯"
```
