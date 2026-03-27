import pytest

from engines.commodity_grouper import (
    BRAND_ALIASES,
    KNOWN_BRANDS,
    NOISE_WORDS,
    WEIGHT_NAME,
    WEIGHT_SPEC,
    WEIGHT_UNIT,
    CommodityGrouper,
    ForbiddenReason,
    MatchScore,
    _fullwidth_to_halfwidth,
    calc_name_similarity,
    calc_spec_overlap,
    calc_unit_match,
    calculate_match_score,
    classify_tokens,
    extract_brand,
    find_spec_conflict,
    generate_match_reason,
    is_auto_group_forbidden,
    normalize_product_name,
    normalize_spec,
    normalize_unit,
)


class TestFullwidthToHalfwidth:
    def test_fullwidth_ascii(self):
        assert _fullwidth_to_halfwidth("ＴｈｉｎｋＰａｄ") == "ThinkPad"

    def test_fullwidth_space(self):
        assert _fullwidth_to_halfwidth("Ａ　Ｂ") == "A B"

    def test_no_change(self):
        assert _fullwidth_to_halfwidth("hello") == "hello"


class TestNormalizeProductName:
    def test_basic_normalization(self):
        result = normalize_product_name(" ThinkPad E14 ")
        assert result == "thinkpad e14"

    def test_fullwidth_conversion(self):
        result = normalize_product_name("ＴｈｉｎｋＰａｄ")
        assert result == "thinkpad"

    def test_bracket_unification(self):
        result = normalize_product_name("联想（ThinkPad）E14")
        assert "(" in result
        assert "（" not in result

    def test_brand_alias_replacement(self):
        result = normalize_product_name("Lenovo ThinkPad E14")
        assert "联想" in result
        assert "lenovo" not in result

    def test_hp_alias(self):
        result = normalize_product_name("HP LaserJet M255dw")
        assert "惠普" in result

    def test_noise_word_removal(self):
        result = normalize_product_name("联想 ThinkPad E14 笔记本电脑")
        assert "笔记本电脑" not in result
        assert "联想" in result
        assert "thinkpad" in result

    def test_noise_removal_preserves_short_name(self):
        """归一化后名称 < 2 字符时不做噪音词移除"""
        result = normalize_product_name("设备")
        assert len(result) >= 2

    def test_empty_input(self):
        assert normalize_product_name("") == ""
        assert normalize_product_name("   ") == ""

    def test_special_punctuation_removal(self):
        result = normalize_product_name("thinkpad-e14.")
        # 连字符保留，句号去除
        assert "thinkpad" in result
        assert "e14" in result
        assert "." not in result

    def test_multiple_spaces_collapsed(self):
        result = normalize_product_name("thinkpad  e14   gen5")
        assert "  " not in result


class TestNormalizeSpec:
    def test_basic_split(self):
        tokens = normalize_spec("i5/16G/512G SSD")
        assert tokens == {"i5", "16g", "512g", "ssd"}

    def test_comma_separated(self):
        tokens = normalize_spec("i5-1235U, 16GB, 512GB")
        assert tokens == {"i5-1235u", "16gb", "512gb"}

    def test_hyphen_preserved(self):
        tokens = normalize_spec("i5-1235U")
        assert "i5-1235u" in tokens

    def test_empty_input(self):
        assert normalize_spec("") == set()
        assert normalize_spec("   ") == set()

    def test_fullwidth_conversion(self):
        tokens = normalize_spec("Ｉ５-1235U／16G")
        assert "i5-1235u" in tokens or "i5" in tokens

    def test_pipe_separator(self):
        tokens = normalize_spec("4K|IPS|27寸")
        assert "4k" in tokens
        assert "ips" in tokens

    def test_pure_punctuation_filtered(self):
        tokens = normalize_spec("a / - / b")
        assert "-" not in tokens
        assert "a" in tokens
        assert "b" in tokens


class TestNormalizeUnit:
    def test_basic(self):
        assert normalize_unit("台") == "台"

    def test_with_spaces(self):
        assert normalize_unit(" 台 ") == "台"

    def test_fullwidth(self):
        result = normalize_unit("ｔ")
        assert result == "t"

    def test_empty(self):
        assert normalize_unit("") == ""

    def test_case_insensitive(self):
        assert normalize_unit("PCS") == "pcs"


class TestExtractBrand:
    def test_known_brand(self):
        assert extract_brand("联想 thinkpad e14") == "联想"

    def test_hp_brand(self):
        assert extract_brand("惠普 laserjet m255dw") == "惠普"

    def test_unknown_brand(self):
        assert extract_brand("unknown brand product") is None

    def test_empty(self):
        assert extract_brand("") is None


class TestBrandAliasTable:
    def test_all_aliases_lowercase(self):
        """所有别名 key 应可在小写化后的文本中匹配"""
        for alias in BRAND_ALIASES:
            assert alias == alias.lower() or any(
                c >= "\u4e00" and c <= "\u9fff" for c in alias
            ), f"非中文别名应为小写: {alias}"

    def test_known_brands_complete(self):
        """KNOWN_BRANDS 应包含所有统一品牌名"""
        assert "联想" in KNOWN_BRANDS
        assert "惠普" in KNOWN_BRANDS
        assert "戴尔" in KNOWN_BRANDS
        assert "华为" in KNOWN_BRANDS
        assert "苹果" in KNOWN_BRANDS
        assert "微软" in KNOWN_BRANDS
        assert "三星" in KNOWN_BRANDS

    def test_at_least_13_brand_groups(self):
        """至少 13 组品牌别名"""
        assert len(KNOWN_BRANDS) >= 13


class TestNoiseWords:
    def test_at_least_20_noise_words(self):
        assert len(NOISE_WORDS) >= 20


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
        assert pytest.approx(1.0) == WEIGHT_NAME + WEIGHT_SPEC + WEIGHT_UNIT

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
