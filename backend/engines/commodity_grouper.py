"""
CommodityGrouper — 商品归组引擎（C+ 保守策略）

本模块为纯业务算法，不依赖 FastAPI/DB。
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

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
    if (quantity_a is not None and quantity_b is not None
            and quantity_a > 0 and quantity_b > 0):
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
        3. 找到最高分的归组，如果 Score >= 0.60 且未命中禁止硬约束 -> 加入
        4. 否则创建新归组
        5. 对每个归组计算置信度和归组理由
        """
        # groups: list of (representative_row, member_rows, scores)
        groups: list[tuple[_NormalizedRow, list[_NormalizedRow], list[MatchScore]]] = []

        for row in rows:
            best_group_idx = -1
            best_score: MatchScore | None = None

            for i, (rep, _members, _scores) in enumerate(groups):
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
                if (score.total >= THRESHOLD_MEDIUM
                        and not forbidden.is_forbidden
                        and (best_score is None or score.total > best_score.total)):
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
