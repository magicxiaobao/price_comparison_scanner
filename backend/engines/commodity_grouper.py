"""
CommodityGrouper — 商品归组引擎（C+ 保守策略）

本模块为纯业务算法，不依赖 FastAPI/DB。
"""

import re

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
