# Task 3.1: CommodityGrouper — 文本归一化 + 品牌别名 + 噪音词

## 输入条件

- Phase 2 完成（标准化流程可用，`standardized_rows` 表有数据）
- `backend/engines/` 目录存在

## 输出物

- 创建: `backend/engines/commodity_grouper.py`（本 Task 仅实现归一化部分，打分和聚合在 Task 3.2 补充）
- 创建: `backend/tests/test_commodity_grouper.py`（本 Task 仅包含归一化测试）

## 禁止修改

- 不修改 `backend/db/schema.sql`（表结构已在 Phase 0 建好）
- 不修改 `backend/engines/__init__.py` 以外的已有 engine 文件
- 不修改 `frontend/`
- 不修改 `backend/api/`（API 路由在 Task 3.3）
- 不修改 `backend/services/`（服务层在 Task 3.3）

## 实现规格

### engines/commodity_grouper.py（归一化部分）

> **MCP 强制规则**：本文件后续 Task 3.2 将引入 `rapidfuzz`，首次使用时**必须**先通过 Context7 查文档确认 `fuzz.token_sort_ratio` 的参数和返回值。

```python
"""
CommodityGrouper — 商品归组引擎（C+ 保守策略）

本模块为纯业务算法，不依赖 FastAPI/DB。
"""

import re
import unicodedata

# ================================================================
# 品牌别名表（内置，MVP 不开放用户编辑）
# ================================================================
BRAND_ALIASES: dict[str, str] = {
    "lenovo": "联想",
    "联想集团": "联想",
    "hp": "惠普",
    "hewlett-packard": "惠普",
    "惠普公司": "惠普",
    "dell": "戴尔",
    "戴尔公司": "戴尔",
    "huawei": "华为",
    "华为技术": "华为",
    "apple": "苹果",
    "苹果公司": "苹果",
    "microsoft": "微软",
    "微软公司": "微软",
    "samsung": "三星",
    "三星电子": "三星",
    "canon": "佳能",
    "佳能公司": "佳能",
    "epson": "爱普生",
    "brother": "兄弟",
    "兄弟公司": "兄弟",
    "cisco": "思科",
    "思科公司": "思科",
    "hikvision": "海康威视",
    "dahua": "大华",
    "大华股份": "大华",
    "asus": "华硕",
    "acer": "宏碁",
}

# 反向映射：所有统一品牌名集合（用于 extract_brand）
KNOWN_BRANDS: set[str] = set(BRAND_ALIASES.values())

# ================================================================
# 噪音词表（内置，MVP 不开放用户编辑）
# ================================================================
NOISE_WORDS: list[str] = [
    "笔记本电脑", "台式电脑", "台式机", "一体机",
    "设备", "产品", "商品", "物资", "物品", "材料", "耗材",
    "采购项", "采购品", "项目",
    "品牌", "型号", "系列",
    "（国产）", "（进口）", "国产", "进口",
    "正品", "全新", "原装", "行货",
]

# ================================================================
# 文本归一化函数
# ================================================================

def _fullwidth_to_halfwidth(text: str) -> str:
    """全角字符转半角"""
    result = []
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:  # 全角空格
            result.append(" ")
        else:
            result.append(char)
    return "".join(result)


def _unify_brackets(text: str) -> str:
    """中文括号统一为半角括号"""
    return text.replace("（", "(").replace("）", ")")


def _collapse_spaces(text: str) -> str:
    """多余空格合并为单个"""
    return re.sub(r"\s+", " ", text).strip()


def _clean_punctuation(text: str) -> str:
    """去除特殊标点，保留括号、斜杠和中文字符"""
    # 保留：字母、数字、中文、空格、括号()、斜杠/、连字符-
    return re.sub(r"[^\w\s()/\-\u4e00-\u9fff]", " ", text)


def _replace_brand_aliases(text: str) -> str:
    """品牌别名替换（在小写化后执行）"""
    # 按别名长度降序排列，优先匹配长别名
    for alias in sorted(BRAND_ALIASES.keys(), key=len, reverse=True):
        if alias in text:
            text = text.replace(alias, BRAND_ALIASES[alias])
    return text


def _remove_noise_words(text: str) -> str:
    """移除噪音词"""
    for word in NOISE_WORDS:
        text = text.replace(word, " ")
    return _collapse_spaces(text)


def normalize_product_name(name: str) -> str:
    """
    商品名称归一化。

    处理顺序：
    1. 去除首尾空格
    2. 全角转半角
    3. 统一为小写
    4. 中英文括号统一为半角
    5. 多余空格合并为单个
    6. 去除特殊标点（保留括号和斜杠）
    7. 品牌别名替换
    8. 噪音词移除（归一化后名称 < 2 字符时不移除）
    """
    if not name:
        return ""

    text = name.strip()
    text = _fullwidth_to_halfwidth(text)
    text = text.lower()
    text = _unify_brackets(text)
    text = _collapse_spaces(text)
    text = _clean_punctuation(text)
    text = _collapse_spaces(text)
    text = _replace_brand_aliases(text)

    # 噪音词移除（归一化后名称过短时保留原始）
    cleaned = _remove_noise_words(text)
    if len(cleaned.replace(" ", "")) < 2:
        return _collapse_spaces(text)
    return cleaned


def normalize_spec(spec: str) -> set[str]:
    """
    规格型号归一化 — 拆分为 token 集合。

    处理：
    1. 全角转半角 + 统一小写
    2. 按分隔符拆分 token（空格、/、|、,、;、+）
    3. 去除纯标点 token 和空字符串
    4. token 内部连字符保留（如 i5-1235u）
    """
    if not spec:
        return set()

    text = _fullwidth_to_halfwidth(spec)
    text = text.lower()

    # 按分隔符拆分
    tokens = re.split(r"[\s/|,;+]+", text)

    # 过滤空字符串和纯标点
    result = set()
    for token in tokens:
        token = token.strip()
        if token and re.search(r"[a-z0-9\u4e00-\u9fff]", token):
            result.add(token)

    return result


def normalize_unit(unit: str) -> str:
    """
    单位归一化 — 仅做文本统一，不做语义换算。

    处理：去除空格、统一小写、全角转半角。
    """
    if not unit:
        return ""
    text = unit.strip()
    text = _fullwidth_to_halfwidth(text)
    text = text.lower()
    return text.replace(" ", "")


def extract_brand(normalized_name: str) -> str | None:
    """
    从归一化后的商品名称中提取已知品牌。

    返回品牌名（如 "联想"），未识别返回 None。
    """
    for brand in KNOWN_BRANDS:
        if brand in normalized_name:
            return brand
    return None
```

**设计要点：**

- 所有函数为纯函数，无副作用，不依赖 FastAPI/DB
- 品牌别名表和噪音词表为模块级常量，写死在代码中
- `BRAND_ALIASES` 的 key 全部小写（因为替换在 `text.lower()` 之后执行）
- `normalize_product_name` 严格按照归组算法文档 3.1 节的 8 步顺序执行
- `normalize_spec` 返回 `set[str]`（不是 list），便于后续 Jaccard 计算
- 噪音词移除后若名称过短（< 2 字符），保留原始名称不做噪音词移除

## 测试与验收

### 测试文件: `backend/tests/test_commodity_grouper.py`

```python
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
| `normalize_product_name(" ThinkPad E14 ")` | `"thinkpad e14"` |
| `normalize_product_name("Lenovo ThinkPad E14 笔记本电脑")` | 包含 `"联想"`，不含 `"lenovo"`，不含 `"笔记本电脑"` |
| `normalize_product_name("HP LaserJet M255dw")` | 包含 `"惠普"` |
| `normalize_spec("i5/16G/512G SSD")` | `{"i5", "16g", "512g", "ssd"}` |
| `normalize_spec("i5-1235U, 16GB, 512GB")` | `{"i5-1235u", "16gb", "512gb"}` |
| `normalize_unit(" 台 ")` | `"台"` |
| `extract_brand("联想 thinkpad e14")` | `"联想"` |
| `extract_brand("unknown product")` | `None` |
| `len(KNOWN_BRANDS)` | `>= 13` |
| `len(NOISE_WORDS)` | `>= 20` |

## 提交

```bash
git add backend/engines/commodity_grouper.py backend/tests/test_commodity_grouper.py
git commit -m "Phase 3.1: CommodityGrouper 文本归一化 — 品牌别名替换 + 噪音词移除 + 规格token化"
```
