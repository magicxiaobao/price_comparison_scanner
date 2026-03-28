import unicodedata
from dataclasses import dataclass


@dataclass
class SupplierPriceData:
    """供应商报价数据"""

    supplier_file_id: str
    supplier_name: str
    unit_price: float | None
    total_price: float | None
    tax_basis: str | None  # 含税 / 不含税 / 未知
    unit: str | None
    currency: str | None  # CNY 等


@dataclass
class AnomalyInfo:
    """异常信息"""

    type: str  # tax_basis_mismatch / unit_mismatch / currency_mismatch / missing_required_field
    description: str
    blocking: bool
    affected_suppliers: list[str]


@dataclass
class ComparisonData:
    """单个商品组的比价结果"""

    group_id: str
    group_name: str
    comparison_status: str  # comparable / blocked / partial
    supplier_prices: list[SupplierPriceData]
    min_price: float | None
    effective_min_price: float | None
    max_price: float | None
    avg_price: float | None
    price_diff: float | None
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
        eligible_supplier_ids: list[str] | None = None,
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
            row = rows[0] if rows else {}
            prices.append(
                SupplierPriceData(
                    supplier_file_id=sid,
                    supplier_name=supplier_name,
                    unit_price=self._safe_float(row.get("unit_price")),
                    total_price=self._safe_float(row.get("total_price")),
                    tax_basis=row.get("tax_basis"),
                    unit=row.get("unit"),
                    currency=row.get("currency", "CNY"),
                )
            )

        # 2. 检测异常
        anomalies = self.detect_anomalies(prices)
        has_anomaly = len(anomalies) > 0
        has_blocking = any(a.blocking for a in anomalies)

        # 3. 计算全量最低价
        valid_prices = [p.unit_price for p in prices if p.unit_price is not None]
        min_price = min(valid_prices) if valid_prices else None
        max_price = max(valid_prices) if valid_prices else None
        avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else None
        price_diff = (
            (max_price - min_price)
            if min_price is not None and max_price is not None
            else None
        )

        # 4. 计算有效最低价
        if eligible_supplier_ids is None:
            effective_min_price = min_price
        elif len(eligible_supplier_ids) == 0:
            effective_min_price = None
        else:
            eligible_prices = [
                p.unit_price
                for p in prices
                if p.unit_price is not None
                and p.supplier_file_id in eligible_supplier_ids
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

    def detect_anomalies(
        self, prices: list[SupplierPriceData]
    ) -> list[AnomalyInfo]:
        """
        异常检测（PRD 5.8）。

        - 税价口径不一致 → 阻断该组最低价结论
        - 单位不一致 → 阻断该组价格比较
        - 币种不一致 → 阻断涉及组的价格比较
        - 必填字段缺失 → 标记不阻断
        """
        anomalies: list[AnomalyInfo] = []

        # 税价口径不一致
        # [C6-fix] 「未知」口径处理策略：
        # - 「未知」不参与一致性比较
        # - 若所有已知口径一致，则不触发异常
        # - 若已知口径不一致，「未知」的存在不改变异常结论
        # - 若所有供应商都是「未知」，则不触发异常
        # - 存在「未知」口径时，在 missing_required_field 异常中提示用户确认
        tax_bases: set[str] = set()
        unknown_tax_suppliers: list[str] = []
        for p in prices:
            if p.tax_basis and p.tax_basis != "未知":
                tax_bases.add(p.tax_basis)
            elif not p.tax_basis or p.tax_basis == "未知":
                unknown_tax_suppliers.append(p.supplier_name)
        if unknown_tax_suppliers and tax_bases:
            anomalies.append(
                AnomalyInfo(
                    type="missing_required_field",
                    description=f"税价口径未明确: {', '.join(unknown_tax_suppliers)}（建议确认后再比价）",
                    blocking=False,
                    affected_suppliers=unknown_tax_suppliers,
                )
            )
        if len(tax_bases) > 1:
            anomalies.append(
                AnomalyInfo(
                    type="tax_basis_mismatch",
                    description=f"税价口径不一致：{', '.join(sorted(tax_bases))}",
                    blocking=True,
                    affected_suppliers=[p.supplier_name for p in prices],
                )
            )

        # [M9] 单位不一致 — 用 NFKC 标准化处理全半角
        units: set[str] = set()
        for p in prices:
            if p.unit:
                normalized = unicodedata.normalize("NFKC", p.unit).strip().lower()
                units.add(normalized)
        if len(units) > 1:
            anomalies.append(
                AnomalyInfo(
                    type="unit_mismatch",
                    description=f"单位不一致：{', '.join(sorted(units))}",
                    blocking=True,
                    affected_suppliers=[p.supplier_name for p in prices],
                )
            )

        # 币种不一致
        currencies: set[str] = set()
        for p in prices:
            if p.currency:
                currencies.add(p.currency.upper())
        if len(currencies) > 1:
            anomalies.append(
                AnomalyInfo(
                    type="currency_mismatch",
                    description=f"币种不一致：{', '.join(sorted(currencies))}",
                    blocking=True,
                    affected_suppliers=[p.supplier_name for p in prices],
                )
            )

        # 必填字段缺失
        for p in prices:
            missing_fields: list[str] = []
            if p.unit_price is None:
                missing_fields.append("单价")
            if not p.unit:
                missing_fields.append("单位")
            if missing_fields:
                anomalies.append(
                    AnomalyInfo(
                        type="missing_required_field",
                        description=f"{p.supplier_name} 缺失: {', '.join(missing_fields)}",
                        blocking=False,
                        affected_suppliers=[p.supplier_name],
                    )
                )

        return anomalies

    def _detect_missing_suppliers(
        self, prices: list[SupplierPriceData]
    ) -> list[str]:
        """检测无报价的供应商"""
        return [p.supplier_name for p in prices if p.unit_price is None]

    def _safe_float(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return None
