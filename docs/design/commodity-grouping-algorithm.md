# 商品归组算法说明

> **文档版本**：v1.0 | **最后更新**：2026-03-26
> **关联文档**：PRD 3.1.8（商品归组候选与人工确认）、技术架构 4.2（CommodityGrouper）

------

## 1. 算法目标与约束

### 1.1 目标

为来自不同供应商的标准化商品行生成候选归组，辅助用户判断「哪些行是同一商品」。

### 1.2 核心约束

- **错归组比漏归组更危险**：宁可多产生独立项让用户手工合并，也不可错误归组
- **规则化、可解释**：每个归组结果必须能用文字说明「为什么归在一起」
- **不使用语义模型**：MVP 不引入 embedding / 向量检索
- **所有归组必须人工确认**：包括高置信归组

------

## 2. 算法流程

```
输入：项目内所有已标准化的商品行（standardized_rows）
      ↓
Step 1：文本归一化（商品名称、规格型号、单位）
      ↓
Step 2：两两配对打分（多因子加权）
      ↓
Step 3：禁止自动归组检查（硬约束过滤）
      ↓
Step 4：置信度分层（高 / 中 / 低）
      ↓
Step 5：聚合为候选归组
      ↓
输出：候选归组列表（含置信度、得分、归组理由）
```

------

## 3. Step 1：文本归一化

所有比较在归一化后的文本上进行，原始值保留不变。

### 3.1 商品名称归一化 `normalize_product_name(name)`

按以下顺序依次处理：

| 步骤 | 操作 | 示例 |
|------|------|------|
| 1 | 去除首尾空格 | `" ThinkPad E14 "` → `"ThinkPad E14"` |
| 2 | 全角转半角 | `"ＴｈｉｎｋＰａｄ"` → `"ThinkPad"` |
| 3 | 统一为小写 | `"ThinkPad E14"` → `"thinkpad e14"` |
| 4 | 中英文括号统一为半角 | `"联想（ThinkPad）"` → `"联想(thinkpad)"` |
| 5 | 多余空格合并为单个 | `"thinkpad  e14"` → `"thinkpad e14"` |
| 6 | 去除特殊标点（但保留括号和斜杠） | `"thinkpad-e14."` → `"thinkpad e14"` |
| 7 | 品牌别名替换（见 3.4） | `"lenovo thinkpad e14"` → `"联想 thinkpad e14"` |
| 8 | 噪音词移除（见 3.5） | `"联想 thinkpad e14 笔记本电脑"` → `"联想 thinkpad e14"` |

### 3.2 规格型号归一化 `normalize_spec(spec)`

规格型号不做整串比较，而是拆分为 **token 集合** 后比较。

| 步骤 | 操作 | 示例 |
|------|------|------|
| 1 | 全角转半角 + 统一小写 | `"Ｉ５-1235U／16G"` → `"i5-1235u/16g"` |
| 2 | 按分隔符拆分 token | 分隔符：空格、`/`、`\|`、`,`、`;`、`+` |
| 3 | 去除纯标点 token | 过滤掉空字符串和纯符号 |
| 4 | token 内部连字符保留 | `"i5-1235u"` 保持不拆 |

**示例**：

| 输入 | token 集合 |
|------|-----------|
| `i5/16G/512G SSD` | `{"i5", "16g", "512g", "ssd"}` |
| `i5-1235U, 16GB, 512GB` | `{"i5-1235u", "16gb", "512gb"}` |
| `ThinkPad E14 Gen5` | `{"thinkpad", "e14", "gen5"}` |

### 3.3 单位归一化 `normalize_unit(unit)`

仅做文本统一，**不做语义等价换算**（如 台≠套）。

| 步骤 | 操作 |
|------|------|
| 1 | 去除空格、统一小写 |
| 2 | 全角转半角 |

单位不一致时直接触发「禁止自动归组」硬约束。

### 3.4 品牌别名表（内置初始集合）

MVP 内置以下品牌别名映射，不开放用户编辑。匹配时忽略大小写。

| 别名 | 统一为 |
|------|--------|
| lenovo, Lenovo, 联想集团 | 联想 |
| hp, HP, hewlett-packard, 惠普公司 | 惠普 |
| dell, Dell, 戴尔公司 | 戴尔 |
| huawei, Huawei, 华为技术 | 华为 |
| apple, Apple, 苹果公司 | 苹果 |
| microsoft, Microsoft, 微软公司 | 微软 |
| samsung, Samsung, 三星电子 | 三星 |
| canon, Canon, 佳能公司 | 佳能 |
| epson, Epson, 爱普生 | 爱普生 |
| brother, Brother, 兄弟公司 | 兄弟 |
| cisco, Cisco, 思科公司 | 思科 |
| hikvision, Hikvision, 海康威视 | 海康威视 |
| dahua, Dahua, 大华股份 | 大华 |

> **扩展说明**：此表在开发和测试过程中根据实际样本逐步补充。后续版本可考虑开放用户编辑。

### 3.5 噪音词表（内置初始集合）

噪音词在归一化时 **移除**，不参与相似度计算。

```
笔记本电脑, 台式电脑, 台式机, 一体机,
设备, 产品, 商品, 物资, 物品, 材料, 耗材,
采购项, 采购品, 项目,
品牌, 型号, 系列,
（国产）, （进口）, 国产, 进口,
正品, 全新, 原装, 行货
```

> **注意**：噪音词移除可能导致误伤（如产品名就叫「XX 设备」）。因此归一化后如果名称为空或过短（< 2 字符），保留原始名称不做噪音词移除。

------

## 4. Step 2：两两配对打分

对项目内所有标准化行进行两两比较，计算匹配得分。

### 4.1 三因子评分模型

| 因子 | 权重 | 计算方式 | 值域 |
|------|------|----------|------|
| 商品名称相似度 `S_name` | 0.50 | 见 4.2 | 0.0 - 1.0 |
| 规格型号 token 重合度 `S_spec` | 0.35 | 见 4.3 | 0.0 - 1.0 |
| 单位一致性 `S_unit` | 0.15 | 见 4.4 | 0.0 或 1.0 |

**综合得分**：

```
Score = S_name × 0.50 + S_spec × 0.35 + S_unit × 0.15
```

### 4.2 商品名称相似度 `S_name`

使用 **归一化后** 的商品名称，采用 rapidfuzz 库的 `token_sort_ratio` 算法。

```python
from rapidfuzz import fuzz

def calc_name_similarity(name_a: str, name_b: str) -> float:
    """
    token_sort_ratio：先将字符串拆分为 token 并排序，再计算编辑距离相似度。
    这样 "联想 thinkpad e14" 和 "thinkpad e14 联想" 能得到高分。
    返回值 0-100，归一化为 0.0-1.0。
    """
    return fuzz.token_sort_ratio(name_a, name_b) / 100.0
```

**为什么选 `token_sort_ratio` 而非 `ratio`**：
- 供应商可能以不同顺序书写同一商品名（「联想 ThinkPad E14」vs「ThinkPad E14 联想」）
- `token_sort_ratio` 对 token 顺序不敏感，更适合本场景

### 4.3 规格型号 token 重合度 `S_spec`

对归一化后的 token 集合计算 **Jaccard 系数**。

```python
def calc_spec_overlap(tokens_a: set, tokens_b: set) -> float:
    """
    Jaccard 系数 = |A ∩ B| / |A ∪ B|
    当两个集合都为空时返回 1.0（视为一致）。
    当仅一方为空时返回 0.0。
    """
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
```

**示例**：

| 行 A token | 行 B token | 交集 | 并集 | S_spec |
|-----------|-----------|------|------|--------|
| {i5, 16g, 512g} | {i5, 16g, 512g} | 3 | 3 | 1.00 |
| {i5, 16g, 512g} | {i5, 8g, 256g} | 1 | 5 | 0.20 |
| {i5, 16g, 512g} | {} | 0 | 3 | 0.00 |
| {} | {} | — | — | 1.00 |

### 4.4 单位一致性 `S_unit`

```python
def calc_unit_match(unit_a: str, unit_b: str) -> float:
    """二值判定：归一化后完全相同返回 1.0，否则 0.0"""
    return 1.0 if normalize_unit(unit_a) == normalize_unit(unit_b) else 0.0
```

### 4.5 完整打分示例

| 场景 | S_name | S_spec | S_unit | Score | 说明 |
|------|--------|--------|--------|-------|------|
| 完全相同 | 1.00 | 1.00 | 1.0 | **1.000** | 名称/型号/单位完全一致 |
| 名称顺序不同 | 0.95 | 1.00 | 1.0 | **0.975** | 「联想 E14」vs「E14 联想」 |
| 名称相似，型号部分匹配 | 0.80 | 0.60 | 1.0 | **0.760** | 品牌相同，配置不完全一致 |
| 名称相似，型号不同 | 0.75 | 0.20 | 1.0 | **0.595** | 同品牌不同型号 |
| 名称相似，单位不同 | 0.90 | 0.80 | 0.0 | **0.730** | 但触发禁止自动归组 |
| 名称完全不同 | 0.20 | 0.00 | 1.0 | **0.250** | 不同商品 |

------

## 5. Step 3：禁止自动归组检查

在打分后、分层前，执行硬约束过滤。**命中任一条即禁止自动归入高置信组**。

```python
def is_auto_group_forbidden(row_a, row_b) -> tuple[bool, str]:
    """返回 (是否禁止, 原因描述)"""

    # 1. 单位不一致
    if normalize_unit(row_a.unit) != normalize_unit(row_b.unit):
        return True, "单位不一致"

    # 2. 规格型号核心 token 冲突
    conflict = find_spec_conflict(row_a.spec_tokens, row_b.spec_tokens)
    if conflict:
        return True, f"型号冲突: {conflict}"

    # 3. 品牌不同
    brand_a = extract_brand(row_a.normalized_name)
    brand_b = extract_brand(row_b.normalized_name)
    if brand_a and brand_b and brand_a != brand_b:
        return True, f"品牌不同: {brand_a} vs {brand_b}"

    # 4. 关键字段低置信且未确认
    if (row_a.confidence < 0.6 and not row_a.is_confirmed) or \
       (row_b.confidence < 0.6 and not row_b.is_confirmed):
        return True, "关键字段低置信且未经用户确认"

    # 5. 数量级差异超过 10 倍
    if row_a.quantity and row_b.quantity:
        ratio = max(row_a.quantity, row_b.quantity) / max(min(row_a.quantity, row_b.quantity), 0.001)
        if ratio > 10:
            return True, f"数量级差异过大: {row_a.quantity} vs {row_b.quantity}"

    return False, ""
```

### 5.1 规格型号核心 token 冲突检测

「核心 token 冲突」定义：两个 token 集合中存在 **同一维度的不同值**。

检测方法：使用正则识别 token 的维度类型，同维度不同值即为冲突。

| 维度 | 正则模式 | 示例 |
|------|----------|------|
| 处理器型号 | `i[3579]-?\d*` | i5 vs i7 → 冲突 |
| 内存容量 | `\d+g[b]?` | 8g vs 16g → 冲突 |
| 存储容量 | `\d+[gt][b]?` （排除已匹配内存的） | 256g vs 512g → 冲突 |
| 型号编号 | `[a-z]\d{2,}` | e14 vs e15 → 冲突 |
| 尺寸 | `\d+寸|\d+inch|\d+"` | 24寸 vs 27寸 → 冲突 |

```python
def find_spec_conflict(tokens_a: set, tokens_b: set) -> str | None:
    """
    检测两个 token 集合是否存在同维度冲突。
    返回冲突描述（如 "i5 vs i7"），无冲突返回 None。
    """
    dims_a = classify_tokens(tokens_a)  # {"cpu": "i5", "ram": "16g", ...}
    dims_b = classify_tokens(tokens_b)

    for dim in dims_a:
        if dim in dims_b and dims_a[dim] != dims_b[dim]:
            return f"{dims_a[dim]} vs {dims_b[dim]}"
    return None
```

### 5.2 品牌提取

从归一化后的商品名称中提取品牌（如果存在）：

```python
KNOWN_BRANDS = {"联想", "惠普", "戴尔", "华为", "苹果", "微软", "三星",
                "佳能", "爱普生", "兄弟", "思科", "海康威视", "大华"}

def extract_brand(normalized_name: str) -> str | None:
    """从归一化名称中提取已知品牌，未识别返回 None"""
    for brand in KNOWN_BRANDS:
        if brand in normalized_name:
            return brand
    return None
```

------

## 6. Step 4：置信度分层

### 6.1 阈值定义

| 置信度 | Score 范围 | 且满足 | 系统行为 |
|--------|-----------|--------|----------|
| **高置信** | Score ≥ 0.85 | 未命中任何禁止自动归组硬约束 | 自动归为候选组 |
| **中置信** | 0.60 ≤ Score < 0.85 | 未命中禁止硬约束（或命中但 Score ≥ 0.60） | 放入「待确认候选」 |
| **低置信** | Score < 0.60 | — | 不建议归组，保持独立 |

**特殊规则**：
- 命中禁止自动归组硬约束的配对，即使 Score ≥ 0.85，也 **降为中置信**（不自动归组，但展示为待确认候选供用户判断）
- Score ≥ 0.60 但命中硬约束的配对，降为中置信并在 `match_reason` 中标注原因

### 6.2 阈值调优说明

以上阈值（0.85 / 0.60）为初始值，将在开发阶段使用标准验收数据集进行调优。调优目标：

| 指标 | 目标 |
|------|------|
| 高置信归组的人工确认无需修改率 | ≥ 90% |
| 高置信归组的误归率（错误归组占比） | ≤ 5% |
| 中置信候选的实际应合并率 | 30% - 70%（过高说明阈值太严，过低说明太松） |

如调优后发现阈值需调整，更新本文档并记录调整理由。

------

## 7. Step 5：聚合为候选归组

### 7.1 聚合算法

采用 **贪心聚类**（非层次聚类），避免过于复杂的算法。

```
1. 将所有商品行按归一化后的商品名称排序
2. 初始化空归组列表
3. 遍历每一行：
   a. 与已有归组的「代表行」逐个计算 Score
   b. 找到最高分的归组，如果 Score ≥ 0.60 且未命中禁止硬约束：
      → 加入该归组
   c. 否则：
      → 创建新归组，当前行作为代表行
4. 对每个归组：
   a. 计算组内最低配对分作为该组的 confidence_level
   b. 生成 match_reason 文本
```

**「代表行」选择**：归组内第一条加入的行（通常是排序后名称最短、最规范的那条）。

### 7.2 归组理由生成 `match_reason`

```python
def generate_match_reason(row_a, row_b, score_detail) -> str:
    """生成可读的归组理由"""
    reasons = []

    if score_detail.name_similarity >= 0.95:
        reasons.append("商品名称几乎一致")
    elif score_detail.name_similarity >= 0.80:
        reasons.append(f"商品名称相似(相似度{score_detail.name_similarity:.0%})")

    if score_detail.spec_overlap >= 0.80:
        reasons.append("规格型号高度匹配")
    elif score_detail.spec_overlap >= 0.50:
        reasons.append(f"规格型号部分匹配(重合度{score_detail.spec_overlap:.0%})")

    if score_detail.unit_match == 1.0:
        reasons.append("单位一致")

    return " + ".join(reasons)
```

**示例输出**：

| 场景 | match_reason |
|------|-------------|
| 完全相同 | `商品名称几乎一致 + 规格型号高度匹配 + 单位一致` |
| 名称相似 | `商品名称相似(相似度85%) + 规格型号部分匹配(重合度60%) + 单位一致` |
| 硬约束降级 | `商品名称几乎一致 + 单位一致 [注意: 型号冲突 i5 vs i7，已降为待确认]` |

------

## 8. 性能考量

### 8.1 复杂度

两两配对打分的时间复杂度为 O(n²)，其中 n 为标准化行总数。

| 行数 | 配对数 | 预估耗时 |
|------|--------|----------|
| 50 | 1,225 | < 100ms |
| 100 | 4,950 | < 500ms |
| 300 | 44,850 | < 3s |
| 500 | 124,750 | < 10s |

### 8.2 优化策略（MVP 阶段可选）

- **预过滤**：归一化后名称完全不同（首字不同或长度差异 > 50%）的配对直接跳过
- **分桶**：按归一化后名称的首字/首词分桶，只在桶内做两两比较
- **提前终止**：如果 S_name < 0.3，跳过后续因子计算

MVP 500 行上限下，暴力 O(n²) 足够使用。当后续版本行数上限提升时再引入优化。

------

## 9. 完整示例

### 输入：3 家供应商，各 3 条商品

| 供应商 | 商品名称 | 规格型号 | 单位 | 单价 |
|--------|----------|----------|------|------|
| A | 联想ThinkPad E14笔记本电脑 | i5/16G/512G | 台 | 4299 |
| A | HP LaserJet打印机 | M255dw | 台 | 2899 |
| A | 显示器27寸 | 4K IPS | 台 | 1899 |
| B | Lenovo E14笔记本 | i5-1235U, 16GB, 512GB SSD | 台 | 4150 |
| B | 惠普激光打印机 | M255dw | 台 | 2950 |
| B | 27寸显示器 | 4K IPS面板 | 台 | 1850 |
| C | thinkpad e14 | i5/16G/512G | 台 | 4200 |
| C | HP 彩色激光打印机 | LaserJet M255dw | 个 | 2880 |
| C | 液晶显示器 27英寸 | 4K | 台 | 1920 |

### 归一化后

| 供应商 | 归一化名称 | 归一化 token | 归一化单位 |
|--------|-----------|-------------|-----------|
| A | `联想 thinkpad e14` | {i5, 16g, 512g} | 台 |
| A | `惠普 laserjet 打印机` | {m255dw} | 台 |
| A | `显示器 27寸` | {4k, ips} | 台 |
| B | `联想 e14` | {i5-1235u, 16gb, 512gb, ssd} | 台 |
| B | `惠普 激光打印机` | {m255dw} | 台 |
| B | `27寸 显示器` | {4k, ips面板} | 台 |
| C | `thinkpad e14` | {i5, 16g, 512g} | 台 |
| C | `惠普 彩色激光打印机` | {laserjet, m255dw} | 个 |
| C | `液晶显示器 27英寸` | {4k} | 台 |

### 打分与归组结果

**归组 1：ThinkPad E14**（高置信）

| 配对 | S_name | S_spec | S_unit | Score | 硬约束 |
|------|--------|--------|--------|-------|--------|
| A-B | 0.82 | 0.33 | 1.0 | 0.68 | 无 |
| A-C | 0.88 | 1.00 | 1.0 | 0.94 | 无 |
| B-C | 0.72 | 0.33 | 1.0 | 0.63 | 无 |

组内最低配对分 0.63，但 A-C 得分 0.94（高置信），B 通过 A 的桥接加入。
最终：**高置信候选组**，理由：`商品名称相似 + 规格型号匹配 + 单位一致 + 品牌均为联想`

**归组 2：惠普打印机 — A+B**（高置信），**C 独立**（硬约束降级）

| 配对 | S_name | S_spec | S_unit | Score | 硬约束 |
|------|--------|--------|--------|-------|--------|
| A-B | 0.85 | 1.00 | 1.0 | 0.93 | 无 |
| A-C | 0.80 | 0.50 | 0.0 | 0.58 | **单位不一致（台 vs 个）** |
| B-C | 0.78 | 0.50 | 0.0 | 0.57 | **单位不一致（台 vs 个）** |

A+B 自动归为高置信候选组。C 因单位不一致（台 vs 个）触发硬约束，保持独立 → 放入 **待确认候选**，标注「单位不一致：台 vs 个」。

**归组 3：显示器**（中置信）

| 配对 | S_name | S_spec | S_unit | Score | 硬约束 |
|------|--------|--------|--------|-------|--------|
| A-B | 0.83 | 0.50 | 1.0 | 0.74 | 无 |
| A-C | 0.62 | 0.50 | 1.0 | 0.64 | 无 |
| B-C | 0.60 | 0.33 | 1.0 | 0.57 | 无 |

组内最低配对分 0.57（B-C），但通过 A 的桥接聚合。最终：**中置信候选组**，理由：`商品名称相似(相似度62%) + 规格型号部分匹配 + 单位一致`。用户需确认。

------

## 10. 参数汇总表

| 参数 | 值 | 说明 |
|------|-----|------|
| 名称相似度权重 | 0.50 | 最重要因子 |
| 规格型号权重 | 0.35 | 次重要因子 |
| 单位一致性权重 | 0.15 | 硬约束补充 |
| 高置信阈值 | ≥ 0.85 | 可自动归为候选组 |
| 中置信阈值 | ≥ 0.60 | 待确认候选 |
| 低置信阈值 | < 0.60 | 保持独立 |
| 低置信字段阈值 | < 0.6 | 字段置信度低于此值视为低置信 |
| 数量级差异倍数 | > 10 | 触发禁止自动归组 |
| 归一化后最短名称 | ≥ 2 字符 | 低于此值不做噪音词移除 |
| 相似度算法 | rapidfuzz.token_sort_ratio | 对 token 顺序不敏感 |
| token 重合度算法 | Jaccard 系数 | 集合交并比 |

> **调优说明**：以上参数为初始值。开发阶段将使用标准验收数据集（PRD 10.5）进行调优，调优结果更新到本表并记录理由。
