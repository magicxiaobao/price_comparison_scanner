import pytest
from engines.commodity_grouper import (
    normalize_product_name,
    normalize_spec,
    normalize_unit,
    extract_brand,
    _fullwidth_to_halfwidth,
    _replace_brand_aliases,
    _remove_noise_words,
    BRAND_ALIASES,
    KNOWN_BRANDS,
    NOISE_WORDS,
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
