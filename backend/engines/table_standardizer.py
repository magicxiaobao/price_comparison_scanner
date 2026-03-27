from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field

from engines.rule_engine import RuleEngine
from models.rule import RuleSet
from models.standardization import (
    HitRuleSnapshot,
    SourceLocation,
    SourceLocationItem,
    StandardizedRowCreate,
)

# 9 个标准字段
STANDARD_FIELDS = [
    "product_name",
    "spec_model",
    "unit",
    "quantity",
    "unit_price",
    "total_price",
    "tax_rate",
    "delivery_period",
    "remark",
]

# 数值型标准字段
NUMERIC_FIELDS = {"quantity", "unit_price", "total_price"}

# 必填字段（缺失时 needs_review=True）
REQUIRED_FIELDS = {"product_name", "unit", "quantity", "unit_price"}

# 税价口径识别关键词
TAX_INCLUSIVE_KEYWORDS = ["含税单价", "含税价", "含税"]
TAX_EXCLUSIVE_KEYWORDS = ["不含税单价", "未税单价", "不含税", "未税"]


@dataclass
class StandardizeResult:
    """standardize() 的返回值"""

    rows: list[StandardizedRowCreate]
    column_mapping: dict[str, str]
    column_mapping_info: list[dict]
    mapping_issues: list[dict] = dc_field(default_factory=list)


class TableStandardizer:
    """
    接收 RawTable 数据 + RuleSet -> 输出 StandardizedRow 列表。
    """

    def __init__(self, rule_engine: RuleEngine) -> None:
        self.rule_engine = rule_engine

    def standardize(
        self,
        raw_table_id: str,
        supplier_file_id: str,
        headers: list[str],
        rows: list[list],
        file_type: str,
        sheet_name: str | None = None,
        page_number: int | None = None,
        table_index: int = 0,
        rules: RuleSet | None = None,
        project_rules: RuleSet | None = None,
    ) -> StandardizeResult:
        if rules is None:
            rules = self.rule_engine.load_global_rules()

        # 1. 列名映射
        column_mapping, hit_snapshots, mapping_issues = self._map_columns(
            headers, rules, project_rules
        )

        # 2. 逐行标准化
        result: list[StandardizedRowCreate] = []
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

        column_mapping_info = self._build_column_mapping_info(
            headers, column_mapping, hit_snapshots, mapping_issues
        )

        return StandardizeResult(
            rows=result,
            column_mapping=column_mapping,
            column_mapping_info=column_mapping_info,
            mapping_issues=mapping_issues,
        )

    def _map_columns(
        self,
        headers: list[str],
        rules: RuleSet,
        project_rules: RuleSet | None,
    ) -> tuple[dict[str, str], list[HitRuleSnapshot], list[dict]]:
        column_mapping: dict[str, str] = {}
        hit_snapshots: list[HitRuleSnapshot] = []
        issues: list[dict] = []

        for header in headers:
            match_result = self.rule_engine.match_column(header, rules, project_rules)
            if match_result.matched and match_result.target_field:
                column_mapping[header] = match_result.target_field
                if match_result.matched_rule:
                    hit_snapshots.append(
                        HitRuleSnapshot(
                            rule_id=match_result.matched_rule.id,
                            rule_name=f"{header}→{match_result.target_field}",
                            match_content=f"{header}→{match_result.target_field}",
                            match_mode=match_result.matched_rule.match_mode.value,
                        )
                    )
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
        field_values: dict[str, object] = {}
        source_location: SourceLocation = {}

        for col_idx, header in enumerate(headers):
            if header not in column_mapping:
                continue
            target_field = column_mapping[header]
            raw_value = row_data[col_idx] if col_idx < len(row_data) else None

            field_values[target_field] = self._normalize_value(
                target_field, raw_value, rules
            )

            source_location[target_field] = self._build_source_location(
                file_type, sheet_name, page_number, table_index, row_index, col_idx
            )

        # 总价自动计算
        if "total_price" not in field_values or field_values.get("total_price") is None:
            qty = field_values.get("quantity")
            price = field_values.get("unit_price")
            if qty is not None and price is not None:
                with contextlib.suppress(ValueError, TypeError):
                    field_values["total_price"] = float(qty) * float(price)  # type: ignore[arg-type]

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
            product_name=self._to_str(field_values.get("product_name")),
            spec_model=self._to_str(field_values.get("spec_model")),
            unit=self._to_str(field_values.get("unit")),
            quantity=self._to_float(field_values.get("quantity")),
            unit_price=self._to_float(field_values.get("unit_price")),
            total_price=self._to_float(field_values.get("total_price")),
            tax_rate=self._to_str(field_values.get("tax_rate")),
            delivery_period=self._to_str(field_values.get("delivery_period")),
            remark=self._to_str(field_values.get("remark")),
            source_location=source_location,
            column_mapping=column_mapping,
            hit_rule_snapshots=hit_snapshots,
            confidence=confidence,
            needs_review=needs_review,
            tax_basis=tax_basis,
        )

    def _normalize_value(
        self, field: str, raw_value: object, rules: RuleSet
    ) -> object:
        """
        值标准化：
        - 数值字段：去除逗号、货币符号、空格后解析
        - 文本字段：strip + 值替换规则
        """
        if raw_value is None:
            return None

        if field in NUMERIC_FIELDS:
            return self._parse_numeric(raw_value)

        # 文本字段
        text = str(raw_value).strip()
        if not text:
            return None

        # 应用值替换规则
        for vn_rule in rules.value_normalization_rules:
            if vn_rule.field == field:
                for pattern in vn_rule.patterns:
                    if pattern in text:
                        text = text.replace(pattern, vn_rule.replace_with)

        return text

    def _detect_tax_basis(
        self, headers: list[str], column_mapping: dict[str, str]
    ) -> str:
        for header, target in column_mapping.items():
            if target == "unit_price":
                header_lower = header.lower().strip()
                # 先检查不含税（更长的关键词优先）
                if any(kw in header_lower for kw in TAX_EXCLUSIVE_KEYWORDS):
                    return "known_exclusive"
                if any(kw in header_lower for kw in TAX_INCLUSIVE_KEYWORDS):
                    return "known_inclusive"
        return "unknown"

    def _build_source_location(
        self,
        file_type: str,
        sheet_name: str | None,
        page_number: int | None,
        table_index: int,
        row_index: int,
        col_index: int,
    ) -> SourceLocationItem:
        if file_type == "xlsx":
            return SourceLocationItem(
                type="xlsx",
                sheet=sheet_name,
                cell=self._index_to_cell(row_index, col_index),
            )
        if file_type == "docx":
            return SourceLocationItem(
                type="docx",
                table_index=table_index,
                row=row_index,
                col=col_index,
            )
        # pdf
        return SourceLocationItem(
            type="pdf",
            page=page_number,
            table_index=table_index,
            row=row_index,
            col=col_index,
            extraction_mode="structure",
        )

    def _build_column_mapping_info(
        self,
        headers: list[str],
        column_mapping: dict[str, str],
        hit_snapshots: list[HitRuleSnapshot],
        issues: list[dict],
    ) -> list[dict]:
        issue_map = {i["header"]: i for i in issues}
        snapshot_map = {
            s.match_content.split("→")[0]: s
            for s in hit_snapshots
            if "→" in s.match_content
        }

        result: list[dict] = []
        for header in headers:
            info: dict = {
                "originalColumn": header,
                "targetField": None,
                "matchedRule": None,
                "matchMode": None,
                "status": "unmapped",
            }
            if header in column_mapping:
                info["targetField"] = column_mapping[header]
                info["status"] = "confirmed"
                if header in snapshot_map:
                    snap = snapshot_map[header]
                    info["matchedRule"] = snap.rule_name
                    info["matchMode"] = snap.match_mode
            if header in issue_map:
                issue = issue_map[header]
                if issue["type"] == "conflict":
                    info["status"] = "conflict"
                elif issue["type"] == "unmapped":
                    info["status"] = "unmapped"
            result.append(info)
        return result

    @staticmethod
    def _index_to_cell(row: int, col: int) -> str:
        col_letter = ""
        c = col
        while c >= 0:
            col_letter = chr(65 + c % 26) + col_letter
            c = c // 26 - 1
        return f"{col_letter}{row + 1}"

    @staticmethod
    def _parse_numeric(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, int | float):
            return float(value)
        text = str(value).strip().replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _to_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")
            return float(str(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_str(value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None
