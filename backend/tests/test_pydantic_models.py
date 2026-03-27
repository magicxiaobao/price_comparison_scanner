"""Task 2.6: Pydantic 模型单元测试"""
import pytest
from pydantic import ValidationError

from models.rule import (
    ColumnMappingRule,
    MatchMode,
    MatchResult,
    RuleCreateUpdate,
    RuleImportSummary,
    RuleSet,
    RuleTestRequest,
    RuleTestResponse,
    RuleType,
    TemplateInfo,
    ValueNormalizationRule,
)
from models.standardization import (
    FieldModifyRequest,
    FieldModifyResponse,
    HitRuleSnapshot,
    SourceLocationItem,
    StandardizedRowCreate,
    StandardizedRowResponse,
    StandardizeRequest,
    StandardizeTaskResponse,
)

# ── rule.py ──


class TestColumnMappingRule:
    def test_from_camel_case_json(self) -> None:
        data = {
            "id": "r1",
            "sourceKeywords": ["单价", "报价"],
            "targetField": "unit_price",
            "matchMode": "exact",
            "priority": 100,
            "createdAt": "2026-03-27T00:00:00Z",
        }
        rule = ColumnMappingRule(**data)
        assert rule.id == "r1"
        assert rule.source_keywords == ["单价", "报价"]
        assert rule.target_field == "unit_price"
        assert rule.match_mode == MatchMode.exact
        assert rule.type == RuleType.column_mapping

    def test_from_snake_case(self) -> None:
        rule = ColumnMappingRule(
            id="r2",
            source_keywords=["数量"],
            target_field="quantity",
            match_mode=MatchMode.fuzzy,
            created_at="2026-03-27T00:00:00Z",
        )
        assert rule.target_field == "quantity"

    def test_serialize_to_camel_case(self) -> None:
        rule = ColumnMappingRule(
            id="r1",
            source_keywords=["单价"],
            target_field="unit_price",
            created_at="2026-03-27T00:00:00Z",
        )
        d = rule.model_dump(by_alias=True)
        assert "sourceKeywords" in d
        assert "targetField" in d
        assert "matchMode" in d
        assert "createdAt" in d

    def test_default_enabled(self) -> None:
        rule = ColumnMappingRule(
            id="r1",
            source_keywords=["单价"],
            target_field="unit_price",
            created_at="2026-03-27T00:00:00Z",
        )
        assert rule.enabled is True


class TestValueNormalizationRule:
    def test_from_camel_case(self) -> None:
        data = {
            "id": "vn1",
            "field": "unit",
            "patterns": ["个", "只"],
            "replaceWith": "个",
            "createdAt": "2026-03-27T00:00:00Z",
        }
        rule = ValueNormalizationRule(**data)
        assert rule.replace_with == "个"
        assert rule.type == RuleType.value_normalization


class TestRuleSet:
    def test_from_full_json(self) -> None:
        data = {
            "version": "1.0",
            "lastUpdated": "2026-03-27T00:00:00Z",
            "columnMappingRules": [
                {
                    "id": "r1",
                    "sourceKeywords": ["单价"],
                    "targetField": "unit_price",
                    "createdAt": "2026-03-27T00:00:00Z",
                }
            ],
            "valueNormalizationRules": [],
        }
        rs = RuleSet(**data)
        assert len(rs.column_mapping_rules) == 1
        assert rs.column_mapping_rules[0].target_field == "unit_price"

    def test_serialize_camel_case(self) -> None:
        rs = RuleSet()
        d = rs.model_dump(by_alias=True)
        assert "columnMappingRules" in d
        assert "valueNormalizationRules" in d
        assert "lastUpdated" in d

    def test_empty_default(self) -> None:
        rs = RuleSet()
        assert rs.column_mapping_rules == []
        assert rs.value_normalization_rules == []


class TestMatchResult:
    def test_unmatched(self) -> None:
        mr = MatchResult(matched=False)
        assert mr.target_field is None
        assert mr.matched_rule is None

    def test_matched_with_rule(self) -> None:
        rule = ColumnMappingRule(
            id="r1",
            source_keywords=["单价"],
            target_field="unit_price",
            created_at="2026-03-27T00:00:00Z",
        )
        mr = MatchResult(matched=True, target_field="unit_price", matched_rule=rule)
        assert mr.matched is True


class TestRuleTestRequestResponse:
    def test_request_camel(self) -> None:
        req = RuleTestRequest(columnName="单价")
        assert req.column_name == "单价"

    def test_response(self) -> None:
        resp = RuleTestResponse(matched=True, targetField="unit_price")
        assert resp.target_field == "unit_price"


class TestRuleImportSummary:
    def test_basic(self) -> None:
        s = RuleImportSummary(total=10, added=8, conflicts=1, skipped=1)
        assert s.total == 10


class TestRuleCreateUpdate:
    def test_column_mapping(self) -> None:
        r = RuleCreateUpdate(
            type=RuleType.column_mapping,
            sourceKeywords=["单价"],
            targetField="unit_price",
        )
        assert r.source_keywords == ["单价"]

    def test_value_normalization(self) -> None:
        r = RuleCreateUpdate(
            type=RuleType.value_normalization,
            field="unit",
            patterns=["个", "只"],
            replaceWith="个",
        )
        assert r.replace_with == "个"


class TestTemplateInfo:
    def test_basic(self) -> None:
        t = TemplateInfo(id="t1", name="通用采购", description="默认模板", ruleCount=15)
        assert t.rule_count == 15


# ── standardization.py ──


class TestSourceLocationItem:
    def test_xlsx_type(self) -> None:
        item = SourceLocationItem(type="xlsx", sheet="Sheet1", cell="B3")
        assert item.type == "xlsx"
        assert item.page is None

    def test_pdf_type(self) -> None:
        item = SourceLocationItem(type="pdf", page=2, table_index=0, row=3, col=1)
        assert item.page == 2

    def test_pdf_ocr_type(self) -> None:
        item = SourceLocationItem(
            type="pdf_ocr", page=1, extraction_mode="ocr", ocr_confidence=0.85
        )
        assert item.ocr_confidence == 0.85


class TestHitRuleSnapshot:
    def test_basic(self) -> None:
        snap = HitRuleSnapshot(
            rule_id="r1", rule_name="单价映射", match_content="报价→unit_price", match_mode="exact"
        )
        assert snap.rule_id == "r1"


class TestStandardizedRowCreate:
    def test_full(self) -> None:
        row = StandardizedRowCreate(
            id="sr1",
            raw_table_id="t1",
            supplier_file_id="f1",
            row_index=0,
            product_name="笔记本电脑",
            unit_price=5999.0,
            quantity=10,
            total_price=59990.0,
            source_location={
                "product_name": SourceLocationItem(type="xlsx", sheet="Sheet1", cell="A2"),
            },
        )
        assert row.product_name == "笔记本电脑"
        assert "product_name" in row.source_location

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            StandardizedRowCreate(id="sr1")  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        row = StandardizedRowCreate(
            id="sr1",
            raw_table_id="t1",
            supplier_file_id="f1",
            row_index=0,
            source_location={},
        )
        assert row.confidence == 1.0
        assert row.needs_review is False
        assert row.product_name is None


class TestStandardizedRowResponse:
    def test_serialize_camel(self) -> None:
        row = StandardizedRowResponse(
            id="sr1",
            rawTableId="t1",
            supplierFileId="f1",
            rowIndex=0,
            sourceLocation={},
        )
        d = row.model_dump(by_alias=True)
        assert "rawTableId" in d
        assert "supplierFileId" in d
        assert "rowIndex" in d
        assert "sourceLocation" in d
        assert "isManuallyModified" in d
        assert "needsReview" in d

    def test_from_snake_case(self) -> None:
        row = StandardizedRowResponse(
            id="sr1",
            raw_table_id="t1",
            supplier_file_id="f1",
            row_index=0,
            source_location={},
        )
        assert row.raw_table_id == "t1"


class TestFieldModifyRequestResponse:
    def test_request(self) -> None:
        req = FieldModifyRequest(field="unit_price", newValue=100.5)
        assert req.new_value == 100.5

    def test_request_null_value(self) -> None:
        req = FieldModifyRequest(field="remark", newValue=None)
        assert req.new_value is None

    def test_response(self) -> None:
        resp = FieldModifyResponse(
            success=True,
            auditLog={"id": "log1"},
            dirtyStages=["grouping", "comparison"],
        )
        assert resp.dirty_stages == ["grouping", "comparison"]


class TestStandardizeRequest:
    def test_default_force_false(self) -> None:
        req = StandardizeRequest()
        assert req.force is False


class TestStandardizeTaskResponse:
    def test_camel(self) -> None:
        resp = StandardizeTaskResponse(taskId="task-123")
        assert resp.task_id == "task-123"
        d = resp.model_dump(by_alias=True)
        assert "taskId" in d
