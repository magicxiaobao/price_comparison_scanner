# Task 3.2: CommodityGrouper — 多因子打分 + 硬约束 + 候选归组生成

## 输入条件

- Task 3.1 完成（`commodity_grouper.py` 已有归一化函数）
- `rapidfuzz` 已在 `requirements.txt` 中声明（Phase 0 已添加）

## 输出物

- 修改: `backend/engines/commodity_grouper.py`（追加打分、硬约束、聚合函数和 `CommodityGrouper` 类）
- 修改: `backend/tests/test_commodity_grouper.py`（追加打分、硬约束、聚合测试）

## 禁止修改

- 不修改 Task 3.1 已实现的归一化函数签名和常量表
- 不修改 `backend/db/`
- 不修改 `backend/api/`
- 不修改 `backend/services/`
- 不修改 `frontend/`

## 实现规格

> **MCP 强制规则**：首次使用 `rapidfuzz` API 时，**必须**先通过 Context7 查文档确认 `fuzz.token_sort_ratio` 的参数签名、返回值范围（0-100）和行为特性。

### 追加到 engines/commodity_grouper.py

```python
from dataclasses import dataclass
from rapidfuzz import fuzz  # ← 首次使用，必须先用 Context7 查文档


# ================================================================
# 权重和阈值常量（写死，MVP 不做配置化）
# ================================================================
WEIGHT_NAME: float = 0.50
WEIGHT_SPEC: float = 0.35
WEIGHT_UNIT: float = 0.15

THRESHOLD_HIGH: float = 0.85
THRESHOLD_MEDIUM: float = 0.60

QUANTITY_RATIO_LIMIT: float = 10.0
FIELD_CONFIDENCE_THRESHOLD: float = 0.6


# ================================================================
# 规格型号维度分类（硬约束冲突检测）
# ================================================================
DIMENSION_PATTERNS: dict[str, str] = {
    "cpu": r"^i[3579]-?\d*",        # 处理器型号
    "ram": r"^\d+g[b]?$",           # 内存容量
    "model": r"^[a-z]\d{2,}$",     # 型号编号（如 e14, e15）
    "size": r"^\d+(寸|inch|\")",    # 尺寸
}


@dataclass
class MatchScore:
    """两行的匹配得分详情"""
    name_similarity: float     # S_name: 0.0 - 1.0
    spec_overlap: float        # S_spec: 0.0 - 1.0
    unit_match: float          # S_unit: 0.0 或 1.0
    total: float               # 加权总分

    @property
    def confidence_level(self) -> str:
        if self.total >= THRESHOLD_HIGH:
            return "high"
        elif self.total >= THRESHOLD_MEDIUM:
            return "medium"
        else:
            return "low"


@dataclass
class ForbiddenReason:
    """禁止自动归组的原因"""
    is_forbidden: bool
    reason: str


@dataclass
class CandidateGroup:
    """候选归组（引擎输出）"""
    group_name: str              # 归组显示名称（取代表行的归一化名称）
    normalized_key: str          # 归一化匹配键
    confidence_level: str        # high / medium / low
    match_score: float           # 组内最低配对分
    match_reason: str            # 可读归组理由
    member_row_ids: list[str]    # 成员 standardized_row_id 列表


# ================================================================
# 打分函数
# ================================================================

def calc_name_similarity(name_a: str, name_b: str) -> float:
    """
    商品名称相似度 — 使用 rapidfuzz 的 token_sort_ratio。

    token_sort_ratio: 先将字符串拆分为 token 并排序，再计算编辑距离相似度。
    返回值 0-100，归一化为 0.0-1.0。
    """
    if not name_a or not name_b:
        return 0.0
    return fuzz.token_sort_ratio(name_a, name_b) / 100.0


def calc_spec_overlap(tokens_a: set[str], tokens_b: set[str]) -> float:
    """
    规格型号 token 重合度 — Jaccard 系数。

    Jaccard = |A ∩ B| / |A ∪ B|
    两集合都为空返回 1.0；仅一方为空返回 0.0。
    """
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def calc_unit_match(unit_a: str, unit_b: str) -> float:
    """单位一致性 — 二值判定：归一化后完全相同返回 1.0，否则 0.0"""
    return 1.0 if normalize_unit(unit_a) == normalize_unit(unit_b) else 0.0


def calculate_match_score(
    name_a: str, name_b: str,
    spec_tokens_a: set[str], spec_tokens_b: set[str],
    unit_a: str, unit_b: str,
) -> MatchScore:
    """计算两行的综合匹配得分"""
    s_name = calc_name_similarity(name_a, name_b)
    s_spec = calc_spec_overlap(spec_tokens_a, spec_tokens_b)
    s_unit = calc_unit_match(unit_a, unit_b)
    total = s_name * WEIGHT_NAME + s_spec * WEIGHT_SPEC + s_unit * WEIGHT_UNIT
    return MatchScore(
        name_similarity=s_name,
        spec_overlap=s_spec,
        unit_match=s_unit,
        total=total,
    )


# ================================================================
# 硬约束检查
# ================================================================

def classify_tokens(tokens: set[str]) -> dict[str, str]:
    """
    将 token 集合按维度分类。

    返回 {"cpu": "i5", "ram": "16g", ...}，同维度只取首个匹配。
    """
    dims: dict[str, str] = {}
    for token in tokens:
        for dim, pattern in DIMENSION_PATTERNS.items():
            if dim not in dims and re.match(pattern, token):
                dims[dim] = token
                break
    return dims


def find_spec_conflict(tokens_a: set[str], tokens_b: set[str]) -> str | None:
    """
    检测两个 token 集合是否存在同维度冲突。

    返回冲突描述（如 "i5 vs i7"），无冲突返回 None。
    """
    dims_a = classify_tokens(tokens_a)
    dims_b = classify_tokens(tokens_b)

    for dim in dims_a:
        if dim in dims_b and dims_a[dim] != dims_b[dim]:
            return f"{dims_a[dim]} vs {dims_b[dim]}"
    return None


def is_auto_group_forbidden(
    normalized_name_a: str, normalized_name_b: str,
    spec_tokens_a: set[str], spec_tokens_b: set[str],
    unit_a: str, unit_b: str,
    confidence_a: float, is_confirmed_a: bool,
    confidence_b: float, is_confirmed_b: bool,
    quantity_a: float | None, quantity_b: float | None,
) -> ForbiddenReason:
    """
    检查是否禁止自动归组（5 条硬约束）。

    返回 ForbiddenReason(is_forbidden=True/False, reason="...")。
    """
    # 1. 单位不一致
    if normalize_unit(unit_a) != normalize_unit(unit_b):
        return ForbiddenReason(True, "单位不一致")

    # 2. 规格型号核心 token 冲突
    conflict = find_spec_conflict(spec_tokens_a, spec_tokens_b)
    if conflict:
        return ForbiddenReason(True, f"型号冲突: {conflict}")

    # 3. 品牌不同
    brand_a = extract_brand(normalized_name_a)
    brand_b = extract_brand(normalized_name_b)
    if brand_a and brand_b and brand_a != brand_b:
        return ForbiddenReason(True, f"品牌不同: {brand_a} vs {brand_b}")

    # 4. 关键字段低置信且未确认
    if (confidence_a < FIELD_CONFIDENCE_THRESHOLD and not is_confirmed_a) or \
       (confidence_b < FIELD_CONFIDENCE_THRESHOLD and not is_confirmed_b):
        return ForbiddenReason(True, "关键字段低置信且未经用户确认")

    # 5. 数量级差异超过 10 倍
    if quantity_a is not None and quantity_b is not None:
        if quantity_a > 0 and quantity_b > 0:
            ratio = max(quantity_a, quantity_b) / min(quantity_a, quantity_b)
            if ratio > QUANTITY_RATIO_LIMIT:
                return ForbiddenReason(
                    True,
                    f"数量级差异过大: {quantity_a} vs {quantity_b}",
                )

    return ForbiddenReason(False, "")


# ================================================================
# 归组理由生成
# ================================================================

def generate_match_reason(score: MatchScore, forbidden: ForbiddenReason | None = None) -> str:
    """生成可读的归组理由"""
    reasons: list[str] = []

    if score.name_similarity >= 0.95:
        reasons.append("商品名称几乎一致")
    elif score.name_similarity >= 0.80:
        reasons.append(f"商品名称相似(相似度{score.name_similarity:.0%})")

    if score.spec_overlap >= 0.80:
        reasons.append("规格型号高度匹配")
    elif score.spec_overlap >= 0.50:
        reasons.append(f"规格型号部分匹配(重合度{score.spec_overlap:.0%})")

    if score.unit_match == 1.0:
        reasons.append("单位一致")

    text = " + ".join(reasons) if reasons else "匹配"

    if forbidden and forbidden.is_forbidden:
        text += f" [注意: {forbidden.reason}，已降为待确认]"

    return text


# ================================================================
# CommodityGrouper 类 — 候选归组生成
# ================================================================

@dataclass
class _NormalizedRow:
    """内部使用的归一化行数据"""
    row_id: str
    normalized_name: str
    spec_tokens: set[str]
    normalized_unit: str
    confidence: float
    is_confirmed: bool
    quantity: float | None


class CommodityGrouper:
    """
    商品归组引擎（C+ 保守策略）。

    算法流程：
    1. 文本归一化（normalize_product_name, normalize_spec, normalize_unit）
    2. 两两配对打分（calculate_match_score）
    3. 禁止自动归组检查（is_auto_group_forbidden）
    4. 置信度分层（THRESHOLD_HIGH, THRESHOLD_MEDIUM）
    5. 贪心聚合为候选归组
    """

    def generate_candidates(self, rows: list[dict]) -> list[CandidateGroup]:
        """
        生成候选归组。

        Args:
            rows: standardized_rows 字典列表，每个 dict 至少包含：
                  id, product_name, spec_model, unit, confidence, is_manually_modified, quantity

        Returns:
            候选归组列表
        """
        if not rows:
            return []

        # Step 1: 归一化
        normalized = self._normalize_rows(rows)

        # 按归一化名称排序
        normalized.sort(key=lambda r: r.normalized_name)

        # Step 2-5: 贪心聚合
        return self._greedy_cluster(normalized)

    def _normalize_rows(self, rows: list[dict]) -> list[_NormalizedRow]:
        """将原始行归一化"""
        result: list[_NormalizedRow] = []
        for row in rows:
            result.append(_NormalizedRow(
                row_id=row["id"],
                normalized_name=normalize_product_name(row.get("product_name", "")),
                spec_tokens=normalize_spec(row.get("spec_model", "")),
                normalized_unit=normalize_unit(row.get("unit", "")),
                confidence=row.get("confidence", 1.0),
                is_confirmed=bool(row.get("is_manually_modified", False)),
                quantity=row.get("quantity"),
            ))
        return result

    def _greedy_cluster(self, rows: list[_NormalizedRow]) -> list[CandidateGroup]:
        """
        贪心聚类算法：

        1. 遍历每一行
        2. 与已有归组的「代表行」逐个计算 Score
        3. 找到最高分的归组，如果 Score >= 0.60 且未命中禁止硬约束 → 加入
        4. 否则创建新归组
        5. 对每个归组计算置信度和归组理由
        """
        # groups: list of (representative_row, member_rows, scores)
        groups: list[tuple[_NormalizedRow, list[_NormalizedRow], list[MatchScore]]] = []

        for row in rows:
            best_group_idx = -1
            best_score: MatchScore | None = None

            for i, (rep, members, scores) in enumerate(groups):
                score = calculate_match_score(
                    rep.normalized_name, row.normalized_name,
                    rep.spec_tokens, row.spec_tokens,
                    rep.normalized_unit, row.normalized_unit,
                )

                forbidden = is_auto_group_forbidden(
                    rep.normalized_name, row.normalized_name,
                    rep.spec_tokens, row.spec_tokens,
                    rep.normalized_unit, row.normalized_unit,
                    rep.confidence, rep.is_confirmed,
                    row.confidence, row.is_confirmed,
                    rep.quantity, row.quantity,
                )

                # 只有 Score >= THRESHOLD_MEDIUM 且未命中硬约束才能加入
                if score.total >= THRESHOLD_MEDIUM and not forbidden.is_forbidden:
                    if best_score is None or score.total > best_score.total:
                        best_group_idx = i
                        best_score = score

            if best_group_idx >= 0 and best_score is not None:
                groups[best_group_idx][1].append(row)
                groups[best_group_idx][2].append(best_score)
            else:
                groups.append((row, [row], []))

        # 转换为 CandidateGroup
        return [self._build_candidate_group(rep, members, scores)
                for rep, members, scores in groups]

    def _build_candidate_group(
        self,
        representative: _NormalizedRow,
        members: list[_NormalizedRow],
        scores: list[MatchScore],
    ) -> CandidateGroup:
        """构建候选归组"""
        if len(members) <= 1:
            # 独立项
            return CandidateGroup(
                group_name=representative.normalized_name,
                normalized_key=representative.normalized_name,
                confidence_level="low",
                match_score=0.0,
                match_reason="独立项，无匹配候选",
                member_row_ids=[representative.row_id],
            )

        # 组内最低配对分决定置信度
        min_score = min(s.total for s in scores) if scores else 0.0
        # 用代表行与最佳匹配的 score 生成理由
        best_score = max(scores, key=lambda s: s.total) if scores else None

        if min_score >= THRESHOLD_HIGH:
            confidence = "high"
        elif min_score >= THRESHOLD_MEDIUM:
            confidence = "medium"
        else:
            confidence = "low"

        reason = generate_match_reason(best_score) if best_score else "匹配"

        return CandidateGroup(
            group_name=representative.normalized_name,
            normalized_key=representative.normalized_name,
            confidence_level=confidence,
            match_score=round(min_score, 4),
            match_reason=reason,
            member_row_ids=[m.row_id for m in members],
        )
```

**设计要点：**

- `CommodityGrouper` 是纯引擎类，不依赖 FastAPI/DB，输入为 dict 列表，输出为 dataclass 列表
- 贪心聚合算法：O(n * k) 其中 k 为当前组数，总体复杂度 O(n^2)，MVP 500 行上限下足够
- 硬约束命中时，即使 Score >= 0.85，该行也不加入该组（保持独立或等待用户手工合并）
- 独立项（只有 1 个成员）的 confidence_level 为 "low"，match_score 为 0.0
- 所有阈值和权重为模块级常量，不做配置化

## 测试与验收

### 追加到 tests/test_commodity_grouper.py

```python
from engines.commodity_grouper import (
    calc_name_similarity,
    calc_spec_overlap,
    calc_unit_match,
    calculate_match_score,
    classify_tokens,
    find_spec_conflict,
    is_auto_group_forbidden,
    generate_match_reason,
    CommodityGrouper,
    MatchScore,
    WEIGHT_NAME, WEIGHT_SPEC, WEIGHT_UNIT,
    THRESHOLD_HIGH, THRESHOLD_MEDIUM,
)


class TestCalcNameSimilarity:
    def test_identical(self):
        score = calc_name_similarity("联想 thinkpad e14", "联想 thinkpad e14")
        assert score >= 0.99

    def test_reordered_tokens(self):
        score = calc_name_similarity("联想 thinkpad e14", "thinkpad e14 联想")
        assert score >= 0.90

    def test_different(self):
        score = calc_name_similarity("联想 thinkpad", "惠普 laserjet")
        assert score < 0.50

    def test_empty(self):
        assert calc_name_similarity("", "test") == 0.0
        assert calc_name_similarity("", "") == 0.0


class TestCalcSpecOverlap:
    def test_identical(self):
        assert calc_spec_overlap({"i5", "16g", "512g"}, {"i5", "16g", "512g"}) == 1.0

    def test_partial(self):
        result = calc_spec_overlap({"i5", "16g", "512g"}, {"i5", "8g", "256g"})
        assert result == pytest.approx(1 / 5)  # Jaccard: 1 / 5

    def test_disjoint(self):
        assert calc_spec_overlap({"a", "b"}, {"c", "d"}) == 0.0

    def test_both_empty(self):
        assert calc_spec_overlap(set(), set()) == 1.0

    def test_one_empty(self):
        assert calc_spec_overlap({"a"}, set()) == 0.0
        assert calc_spec_overlap(set(), {"a"}) == 0.0


class TestCalcUnitMatch:
    def test_same(self):
        assert calc_unit_match("台", "台") == 1.0

    def test_different(self):
        assert calc_unit_match("台", "个") == 0.0

    def test_case_insensitive(self):
        assert calc_unit_match("PCS", "pcs") == 1.0


class TestCalculateMatchScore:
    def test_perfect_match(self):
        score = calculate_match_score(
            "联想 thinkpad e14", "联想 thinkpad e14",
            {"i5", "16g"}, {"i5", "16g"},
            "台", "台",
        )
        assert score.total >= 0.95
        assert score.confidence_level == "high"

    def test_weights_sum_to_one(self):
        assert WEIGHT_NAME + WEIGHT_SPEC + WEIGHT_UNIT == pytest.approx(1.0)

    def test_score_range(self):
        score = calculate_match_score("a", "b", {"x"}, {"y"}, "台", "个")
        assert 0.0 <= score.total <= 1.0


class TestClassifyTokens:
    def test_cpu_detection(self):
        dims = classify_tokens({"i5", "16g", "512g"})
        assert dims.get("cpu") == "i5"

    def test_ram_detection(self):
        dims = classify_tokens({"16g"})
        assert dims.get("ram") == "16g"

    def test_model_detection(self):
        dims = classify_tokens({"e14"})
        assert dims.get("model") == "e14"


class TestFindSpecConflict:
    def test_cpu_conflict(self):
        result = find_spec_conflict({"i5", "16g"}, {"i7", "16g"})
        assert result is not None
        assert "i5" in result and "i7" in result

    def test_no_conflict(self):
        assert find_spec_conflict({"i5", "16g"}, {"i5", "16g"}) is None

    def test_model_conflict(self):
        result = find_spec_conflict({"e14"}, {"e15"})
        assert result is not None

    def test_empty_sets(self):
        assert find_spec_conflict(set(), set()) is None


class TestIsAutoGroupForbidden:
    def test_unit_mismatch(self):
        result = is_auto_group_forbidden(
            "a", "b", set(), set(), "台", "个",
            1.0, True, 1.0, True, None, None,
        )
        assert result.is_forbidden
        assert "单位不一致" in result.reason

    def test_spec_conflict(self):
        result = is_auto_group_forbidden(
            "a", "b", {"i5"}, {"i7"}, "台", "台",
            1.0, True, 1.0, True, None, None,
        )
        assert result.is_forbidden
        assert "型号冲突" in result.reason

    def test_brand_different(self):
        result = is_auto_group_forbidden(
            "联想 thinkpad", "惠普 laserjet", set(), set(), "台", "台",
            1.0, True, 1.0, True, None, None,
        )
        assert result.is_forbidden
        assert "品牌不同" in result.reason

    def test_low_confidence_unconfirmed(self):
        result = is_auto_group_forbidden(
            "a", "b", set(), set(), "台", "台",
            0.3, False, 1.0, True, None, None,
        )
        assert result.is_forbidden
        assert "低置信" in result.reason

    def test_quantity_ratio(self):
        result = is_auto_group_forbidden(
            "a", "b", set(), set(), "台", "台",
            1.0, True, 1.0, True, 1.0, 100.0,
        )
        assert result.is_forbidden
        assert "数量级差异" in result.reason

    def test_no_constraint(self):
        result = is_auto_group_forbidden(
            "联想 thinkpad", "联想 thinkpad", {"i5"}, {"i5"}, "台", "台",
            1.0, True, 1.0, True, 10.0, 10.0,
        )
        assert not result.is_forbidden


class TestGenerateMatchReason:
    def test_high_similarity(self):
        score = MatchScore(0.96, 0.90, 1.0, 0.95)
        reason = generate_match_reason(score)
        assert "几乎一致" in reason
        assert "高度匹配" in reason
        assert "单位一致" in reason

    def test_with_forbidden(self):
        score = MatchScore(0.96, 0.90, 0.0, 0.80)
        forbidden = ForbiddenReason(True, "单位不一致")
        reason = generate_match_reason(score, forbidden)
        assert "降为待确认" in reason


class TestCommodityGrouper:
    def test_empty_input(self):
        grouper = CommodityGrouper()
        assert grouper.generate_candidates([]) == []

    def test_single_row(self):
        grouper = CommodityGrouper()
        rows = [{"id": "r1", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G", "unit": "台"}]
        groups = grouper.generate_candidates(rows)
        assert len(groups) == 1
        assert groups[0].confidence_level == "low"  # 独立项
        assert len(groups[0].member_row_ids) == 1

    def test_identical_rows_grouped(self):
        grouper = CommodityGrouper()
        rows = [
            {"id": "r1", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G/512G", "unit": "台"},
            {"id": "r2", "product_name": "Lenovo ThinkPad E14", "spec_model": "i5/16G/512G", "unit": "台"},
        ]
        groups = grouper.generate_candidates(rows)
        # 两行应归为同一组
        grouped = [g for g in groups if len(g.member_row_ids) > 1]
        assert len(grouped) >= 1
        assert set(grouped[0].member_row_ids) == {"r1", "r2"}

    def test_unit_mismatch_not_grouped(self):
        grouper = CommodityGrouper()
        rows = [
            {"id": "r1", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G", "unit": "台"},
            {"id": "r2", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G", "unit": "个"},
        ]
        groups = grouper.generate_candidates(rows)
        # 单位不一致，不应自动归组
        for g in groups:
            assert len(g.member_row_ids) == 1

    def test_different_products_separate(self):
        grouper = CommodityGrouper()
        rows = [
            {"id": "r1", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G", "unit": "台"},
            {"id": "r2", "product_name": "惠普 LaserJet M255dw", "spec_model": "M255dw", "unit": "台"},
        ]
        groups = grouper.generate_candidates(rows)
        assert len(groups) == 2
        for g in groups:
            assert len(g.member_row_ids) == 1

    def test_three_suppliers_same_product(self):
        """验收数据集核心场景：3 家供应商同一商品"""
        grouper = CommodityGrouper()
        rows = [
            {"id": "r1", "product_name": "联想ThinkPad E14笔记本电脑", "spec_model": "i5/16G/512G", "unit": "台",
             "confidence": 1.0},
            {"id": "r2", "product_name": "Lenovo E14笔记本", "spec_model": "i5-1235U, 16GB, 512GB SSD", "unit": "台",
             "confidence": 1.0},
            {"id": "r3", "product_name": "thinkpad e14", "spec_model": "i5/16G/512G", "unit": "台",
             "confidence": 1.0},
        ]
        groups = grouper.generate_candidates(rows)
        # 至少 r1 和 r3 应该归在一起（名称和规格高度匹配）
        large_groups = [g for g in groups if len(g.member_row_ids) >= 2]
        assert len(large_groups) >= 1

    def test_confidence_level_assignment(self):
        grouper = CommodityGrouper()
        rows = [
            {"id": "r1", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G/512G", "unit": "台"},
            {"id": "r2", "product_name": "联想 ThinkPad E14", "spec_model": "i5/16G/512G", "unit": "台"},
        ]
        groups = grouper.generate_candidates(rows)
        grouped = [g for g in groups if len(g.member_row_ids) > 1]
        assert len(grouped) == 1
        assert grouped[0].confidence_level in ("high", "medium")

    def test_match_reason_not_empty(self):
        grouper = CommodityGrouper()
        rows = [
            {"id": "r1", "product_name": "联想 E14", "spec_model": "i5", "unit": "台"},
            {"id": "r2", "product_name": "联想 E14", "spec_model": "i5", "unit": "台"},
        ]
        groups = grouper.generate_candidates(rows)
        for g in groups:
            assert g.match_reason != ""
```

### 门禁命令

```bash
cd backend
ruff check engines/commodity_grouper.py
mypy engines/commodity_grouper.py --ignore-missing-imports
pytest tests/test_commodity_grouper.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| `calc_name_similarity("联想 thinkpad e14", "联想 thinkpad e14")` | `>= 0.99` |
| `calc_name_similarity("联想 thinkpad e14", "thinkpad e14 联想")` | `>= 0.90` |
| `calc_spec_overlap({"i5","16g","512g"}, {"i5","8g","256g"})` | `0.2` (1/5) |
| `calc_unit_match("台", "个")` | `0.0` |
| `WEIGHT_NAME + WEIGHT_SPEC + WEIGHT_UNIT` | `1.0` |
| 单位不一致 → `is_auto_group_forbidden` | `is_forbidden == True` |
| 规格冲突（i5 vs i7）→ `is_auto_group_forbidden` | `is_forbidden == True` |
| 品牌不同 → `is_auto_group_forbidden` | `is_forbidden == True` |
| 数量级差异 > 10 倍 → `is_auto_group_forbidden` | `is_forbidden == True` |
| 3 家供应商同一商品 → 至少 2 行归为一组 | `len(member_row_ids) >= 2` |
| 独立项 | `confidence_level == "low"`, `match_score == 0.0` |

## 提交

```bash
git add backend/engines/commodity_grouper.py backend/tests/test_commodity_grouper.py
git commit -m "Phase 3.2: CommodityGrouper 多因子打分 + 5条硬约束 + 贪心聚合候选归组生成"
```
