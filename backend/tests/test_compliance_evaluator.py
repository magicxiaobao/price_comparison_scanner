from __future__ import annotations

from engines.compliance_evaluator import ComplianceEvaluator


class TestComplianceEvaluator:
    def setup_method(self) -> None:
        self.engine = ComplianceEvaluator()

    def test_keyword_match_found(self) -> None:
        req = {"match_type": "keyword", "expected_value": "DDR5"}
        rows = [{"product_name": "ThinkPad E14", "spec_model": "DDR5 16GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "match"
        assert result.needs_review is False

    def test_keyword_match_not_found(self) -> None:
        req = {"match_type": "keyword", "expected_value": "DDR5"}
        rows = [{"product_name": "ThinkPad E14", "spec_model": "DDR4 8GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
        assert result.needs_review is True

    def test_keyword_case_insensitive(self) -> None:
        req = {"match_type": "keyword", "expected_value": "ssd"}
        rows = [{"product_name": "笔记本", "spec_model": "512GB SSD", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "match"

    def test_numeric_match_gte_pass(self) -> None:
        req = {"match_type": "numeric", "expected_value": "16", "operator": "gte"}
        rows = [{"product_name": "笔记本", "spec_model": "内存32GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "match"

    def test_numeric_match_gte_fail(self) -> None:
        req = {"match_type": "numeric", "expected_value": "16", "operator": "gte"}
        rows = [{"product_name": "笔记本", "spec_model": "内存8GB", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "no_match"

    def test_numeric_no_number_found(self) -> None:
        req = {"match_type": "numeric", "expected_value": "16", "operator": "gte"}
        rows = [{"product_name": "笔记本", "spec_model": "大容量内存", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
        assert result.needs_review is True

    def test_manual_always_unclear(self) -> None:
        req = {"match_type": "manual", "expected_value": "需人工判断"}
        rows = [{"product_name": "test", "spec_model": "test", "remark": "test"}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
        assert result.needs_review is True

    def test_keyword_empty_expected_value(self) -> None:
        req = {"match_type": "keyword", "expected_value": ""}
        rows = [{"product_name": "test", "spec_model": "test", "remark": ""}]
        result = self.engine.evaluate_single(req, rows, "sf1")
        assert result.status == "unclear"
