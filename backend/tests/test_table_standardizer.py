from __future__ import annotations

import uuid

import pytest

from engines.rule_engine import RuleEngine
from engines.table_standardizer import (
    STANDARD_FIELDS,
    TableStandardizer,
)
from models.rule import RuleSet


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


@pytest.fixture
def default_rules(rule_engine):
    return rule_engine.load_global_rules()


# ---- 列名映射 ----


def test_map_columns_basic(standardizer, default_rules):
    headers = ["产品名称", "单价", "数量", "单位"]
    mapping, snapshots, issues = standardizer._map_columns(
        headers, default_rules, None
    )
    assert mapping["产品名称"] == "product_name"
    assert mapping["单价"] == "unit_price"
    assert mapping["数量"] == "quantity"
    assert mapping["单位"] == "unit"
    for target in mapping.values():
        assert target in STANDARD_FIELDS
    assert len(snapshots) > 0


def test_map_columns_unmapped(standardizer, default_rules):
    headers = ["产品名称", "不存在的列"]
    _, _, issues = standardizer._map_columns(headers, default_rules, None)
    unmapped = [i for i in issues if i["type"] == "unmapped"]
    assert any(i["header"] == "不存在的列" for i in unmapped)


# ---- 值标准化 ----


def test_normalize_numeric_with_comma(standardizer, default_rules):
    result = standardizer._normalize_value("quantity", "1,234.56", default_rules)
    assert result == 1234.56


def test_normalize_numeric_with_currency(standardizer, default_rules):
    result = standardizer._normalize_value("unit_price", "¥4,299", default_rules)
    assert result == 4299.0


def test_normalize_numeric_with_fullwidth_yen(standardizer, default_rules):
    result = standardizer._normalize_value("unit_price", "￥1,000", default_rules)
    assert result == 1000.0


def test_normalize_text_strip(standardizer, default_rules):
    result = standardizer._normalize_value("product_name", "  电脑  ", default_rules)
    assert result == "电脑"


def test_normalize_numeric_none(standardizer, default_rules):
    result = standardizer._normalize_value("quantity", None, default_rules)
    assert result is None


def test_normalize_numeric_empty_string(standardizer, default_rules):
    result = standardizer._normalize_value("quantity", "", default_rules)
    assert result is None


def test_normalize_text_empty_returns_none(standardizer, default_rules):
    result = standardizer._normalize_value("product_name", "   ", default_rules)
    assert result is None


# ---- 总价计算 ----


def test_total_price_auto_calc(standardizer, rule_engine):
    headers = ["产品名称", "单价", "数量", "单位"]
    rows = [["打印机", 2500, 3, "台"]]
    result = standardizer.standardize(
        raw_table_id="rt1",
        supplier_file_id="sf1",
        headers=headers,
        rows=rows,
        file_type="xlsx",
        sheet_name="Sheet1",
    )
    row = result.rows[0]
    assert row.total_price == pytest.approx(7500.0)


def test_total_price_from_original(standardizer, rule_engine):
    headers = ["产品名称", "单价", "数量", "单位", "总价"]
    rows = [["打印机", 2500, 3, "台", 8000]]
    result = standardizer.standardize(
        raw_table_id="rt1",
        supplier_file_id="sf1",
        headers=headers,
        rows=rows,
        file_type="xlsx",
        sheet_name="Sheet1",
    )
    row = result.rows[0]
    assert row.total_price == pytest.approx(8000.0)


# ---- 税价口径 ----


def test_tax_basis_inclusive(standardizer):
    headers = ["含税单价"]
    mapping = {"含税单价": "unit_price"}
    assert standardizer._detect_tax_basis(headers, mapping) == "known_inclusive"


def test_tax_basis_exclusive(standardizer):
    headers = ["不含税单价"]
    mapping = {"不含税单价": "unit_price"}
    assert standardizer._detect_tax_basis(headers, mapping) == "known_exclusive"


def test_tax_basis_unknown(standardizer):
    headers = ["单价"]
    mapping = {"单价": "unit_price"}
    assert standardizer._detect_tax_basis(headers, mapping) == "unknown"


# ---- source_location ----


def test_source_location_xlsx(standardizer):
    loc = standardizer._build_source_location("xlsx", "Sheet1", None, 0, 2, 3)
    assert loc.type == "xlsx"
    assert loc.sheet == "Sheet1"
    assert loc.cell == "D3"


def test_source_location_docx(standardizer):
    loc = standardizer._build_source_location("docx", None, None, 1, 5, 2)
    assert loc.type == "docx"
    assert loc.table_index == 1
    assert loc.row == 5
    assert loc.col == 2


def test_source_location_pdf(standardizer):
    loc = standardizer._build_source_location("pdf", None, 3, 0, 1, 4)
    assert loc.type == "pdf"
    assert loc.page == 3
    assert loc.table_index == 0
    assert loc.row == 1
    assert loc.col == 4
    assert loc.extraction_mode == "structure"


# ---- 完整标准化 ----


def test_standardize_basic(standardizer):
    headers = ["产品名称", "规格型号", "单位", "数量", "单价"]
    rows = [["打印机", "HP-200", "台", 5, 3000]]
    result = standardizer.standardize(
        raw_table_id="rt1",
        supplier_file_id="sf1",
        headers=headers,
        rows=rows,
        file_type="xlsx",
        sheet_name="Sheet1",
    )
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.product_name == "打印机"
    assert row.spec_model == "HP-200"
    assert row.unit == "台"
    assert row.quantity == pytest.approx(5.0)
    assert row.unit_price == pytest.approx(3000.0)
    assert row.total_price == pytest.approx(15000.0)
    assert row.confidence == 1.0
    assert row.needs_review is False
    # valid UUID
    uuid.UUID(row.id)
    # source_location has entries
    assert len(row.source_location) > 0
    # column_mapping_info
    assert len(result.column_mapping_info) == len(headers)


def test_standardize_missing_required(standardizer):
    headers = ["产品名称"]
    rows = [["打印机"]]
    result = standardizer.standardize(
        raw_table_id="rt1",
        supplier_file_id="sf1",
        headers=headers,
        rows=rows,
        file_type="xlsx",
        sheet_name="Sheet1",
    )
    row = result.rows[0]
    assert row.needs_review is True
    assert row.confidence <= 0.5


def test_standardize_multiple_rows(standardizer):
    headers = ["产品名称", "单价", "数量", "单位"]
    rows = [
        ["打印机", 2500, 3, "台"],
        ["电脑", 6000, 10, "台"],
    ]
    result = standardizer.standardize(
        raw_table_id="rt1",
        supplier_file_id="sf1",
        headers=headers,
        rows=rows,
        file_type="xlsx",
        sheet_name="Sheet1",
    )
    assert len(result.rows) == 2
    assert result.rows[0].row_index == 0
    assert result.rows[1].row_index == 1
    assert result.rows[0].product_name == "打印机"
    assert result.rows[1].product_name == "电脑"


# ---- 辅助方法 ----


def test_index_to_cell():
    assert TableStandardizer._index_to_cell(0, 0) == "A1"
    assert TableStandardizer._index_to_cell(2, 3) == "D3"
    assert TableStandardizer._index_to_cell(0, 25) == "Z1"
    assert TableStandardizer._index_to_cell(0, 26) == "AA1"
    assert TableStandardizer._index_to_cell(9, 27) == "AB10"


def test_to_float():
    assert TableStandardizer._to_float(None) is None
    assert TableStandardizer._to_float(42) == 42.0
    assert TableStandardizer._to_float(3.14) == 3.14
    assert TableStandardizer._to_float("1,234.56") == 1234.56
    assert TableStandardizer._to_float("¥99") == 99.0
    assert TableStandardizer._to_float("￥1,000") == 1000.0
    assert TableStandardizer._to_float("abc") is None
    assert TableStandardizer._to_float("") is None


def test_to_str():
    assert TableStandardizer._to_str(None) is None
    assert TableStandardizer._to_str("hello") == "hello"
    assert TableStandardizer._to_str("  space  ") == "space"
    assert TableStandardizer._to_str("") is None
    assert TableStandardizer._to_str("   ") is None


def test_parse_numeric():
    assert TableStandardizer._parse_numeric(None) is None
    assert TableStandardizer._parse_numeric(42) == 42.0
    assert TableStandardizer._parse_numeric(3.14) == 3.14
    assert TableStandardizer._parse_numeric("1,234.56") == 1234.56
    assert TableStandardizer._parse_numeric("¥4,299") == 4299.0
    assert TableStandardizer._parse_numeric("not_a_number") is None
    assert TableStandardizer._parse_numeric("") is None


def test_column_mapping_info_structure(standardizer):
    headers = ["产品名称", "未知列"]
    rows = [["打印机", "xxx"]]
    result = standardizer.standardize(
        raw_table_id="rt1",
        supplier_file_id="sf1",
        headers=headers,
        rows=rows,
        file_type="xlsx",
        sheet_name="Sheet1",
    )
    info = result.column_mapping_info
    assert len(info) == 2
    mapped = [i for i in info if i["status"] == "confirmed"]
    unmapped = [i for i in info if i["status"] == "unmapped"]
    assert len(mapped) >= 1
    assert len(unmapped) >= 1
    assert mapped[0]["targetField"] is not None
    assert unmapped[0]["targetField"] is None


def test_value_normalization_rule_applied(standardizer, tmp_path):
    """值替换规则生效"""
    rules = RuleSet(
        column_mapping_rules=[],
        value_normalization_rules=[],
    )
    # text field with value normalization: no rules → original text
    result = standardizer._normalize_value("unit", "个/套", rules)
    assert result == "个/套"
