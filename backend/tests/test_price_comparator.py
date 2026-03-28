from engines.price_comparator import PriceComparator, SupplierPriceData


class TestPriceComparator:
    def setup_method(self) -> None:
        self.engine = PriceComparator()

    def test_basic_comparison(self) -> None:
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

    def test_effective_min_with_eligible(self) -> None:
        group = {"id": "g1", "group_name": "ThinkPad E14"}
        rows = {
            "sf1": [{"supplier_name": "联想", "unit_price": 4299, "unit": "台", "currency": "CNY"}],
            "sf2": [{"supplier_name": "戴尔", "unit_price": 4599, "unit": "台", "currency": "CNY"}],
            "sf3": [{"supplier_name": "惠普", "unit_price": 4199, "unit": "台", "currency": "CNY"}],
        }
        # 惠普不符合需求，仅联想和戴尔参与有效最低价
        result = self.engine.compare_group(group, rows, eligible_supplier_ids=["sf1", "sf2"])
        assert result.min_price == 4199  # 全量最低价
        assert result.effective_min_price == 4299  # 有效最低价

    def test_tax_basis_mismatch(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "tax_basis": "含税", "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "tax_basis": "不含税", "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.has_anomaly is True
        assert result.comparison_status == "blocked"
        assert any(a.type == "tax_basis_mismatch" for a in result.anomaly_details)

    def test_unit_mismatch(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "unit": "套"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.comparison_status == "blocked"
        assert any(a.type == "unit_mismatch" for a in result.anomaly_details)

    def test_unit_fullwidth_halfwidth_normalized(self) -> None:
        """[M9] 全角「台」和半角「台」应被视为相同单位"""
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "\uff54\uff41\uff49"}],  # 全角 ｔａｉ
            "sf2": [{"supplier_name": "B", "unit_price": 90, "unit": "tai"}],  # 半角
        }
        result = self.engine.compare_group(group, rows)
        assert not any(a.type == "unit_mismatch" for a in result.anomaly_details)

    def test_currency_mismatch(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台", "currency": "CNY"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "unit": "台", "currency": "USD"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.comparison_status == "blocked"
        assert any(a.type == "currency_mismatch" for a in result.anomaly_details)

    def test_missing_required_field(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows: dict[str, list[dict]] = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": None, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert any(a.type == "missing_required_field" for a in result.anomaly_details)
        # 必填缺失不阻断
        assert not any(a.blocking and a.type == "missing_required_field" for a in result.anomaly_details)

    def test_no_eligible_suppliers(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows, eligible_supplier_ids=[])
        assert result.effective_min_price is None

    def test_missing_suppliers_detected(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows: dict[str, list[dict]] = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": None, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert "B" in result.missing_suppliers

    def test_unknown_tax_basis_no_block(self) -> None:
        """[C6] 所有供应商都是「未知」口径 → 不触发 tax_basis_mismatch"""
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "tax_basis": "未知", "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "tax_basis": "未知", "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert not any(a.type == "tax_basis_mismatch" for a in result.anomaly_details)

    def test_unknown_tax_basis_with_known_warns(self) -> None:
        """[C6] 有已知口径 + 未知口径 → missing_required_field 提示但不阻断"""
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "tax_basis": "含税", "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": 90, "tax_basis": "未知", "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        tax_warn = [a for a in result.anomaly_details if a.type == "missing_required_field" and "税价口径" in a.description]
        assert len(tax_warn) == 1
        assert tax_warn[0].blocking is False

    def test_empty_supplier_rows(self) -> None:
        """边界：空 supplier_rows_map"""
        group = {"id": "g1", "group_name": "test"}
        result = self.engine.compare_group(group, {})
        assert result.min_price is None
        assert result.max_price is None
        assert result.avg_price is None
        assert result.comparison_status == "comparable"

    def test_all_suppliers_missing_price(self) -> None:
        """边界：所有供应商无报价"""
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": None, "unit": "台"}],
            "sf2": [{"supplier_name": "B", "unit_price": None, "unit": "台"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.min_price is None
        assert result.effective_min_price is None
        assert len(result.missing_suppliers) == 2

    def test_avg_price_calculation(self) -> None:
        group = {"id": "g1", "group_name": "test"}
        rows = {
            "sf1": [{"supplier_name": "A", "unit_price": 100, "unit": "台", "tax_basis": "含税"}],
            "sf2": [{"supplier_name": "B", "unit_price": 200, "unit": "台", "tax_basis": "含税"}],
        }
        result = self.engine.compare_group(group, rows)
        assert result.avg_price == 150.0
        assert result.price_diff == 100.0

    def test_detect_anomalies_directly(self) -> None:
        prices = [
            SupplierPriceData("sf1", "A", 100.0, None, "含税", "台", "CNY"),
            SupplierPriceData("sf2", "B", 90.0, None, "含税", "台", "CNY"),
        ]
        anomalies = self.engine.detect_anomalies(prices)
        assert len(anomalies) == 0

    def test_safe_float_edge_cases(self) -> None:
        assert self.engine._safe_float(None) is None
        assert self.engine._safe_float("abc") is None
        assert self.engine._safe_float("123.45") == 123.45
        assert self.engine._safe_float(0) == 0.0
