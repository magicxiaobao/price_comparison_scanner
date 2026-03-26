# Task 2.2: RuleEngine — 规则加载/管理/冲突解决

## 输入条件

- Phase 1 完成
- Task 2.6 完成（`models/rule.py` 中 `RuleSet`、`ColumnMappingRule`、`MatchResult` 等模型已定义）
- 技术架构 3.1 规则 JSON 结构已确定
- 技术架构 4.2 RuleEngine 类结构已确定

## 输出物

- 创建: `backend/engines/rule_engine.py`
- 创建: `backend/tests/test_rule_engine.py`

## 禁止修改

- 不修改 `db/schema.sql`
- 不修改 `db/database.py`
- 不修改 `api/` 目录（API 在 Task 2.3 实现）
- 不修改 `frontend/`

## 实现规格

### engines/rule_engine.py

```python
import json
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from models.rule import (
    RuleSet, ColumnMappingRule, ValueNormalizationRule,
    MatchResult, MatchMode, RuleSource,
)

# 标准字段白名单
STANDARD_FIELDS = [
    "product_name", "spec_model", "unit", "quantity",
    "unit_price", "total_price", "tax_rate",
    "delivery_period", "remark",
]

class RuleEngine:
    """
    全局规则 + 项目覆盖，含冲突解决。
    规则存储在 app_data/rules/ 下的 JSON 文件。
    """

    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir
        self.rules_dir.mkdir(parents=True, exist_ok=True)

    # ---- 规则加载 ----

    def load_global_rules(self) -> RuleSet:
        """加载用户自定义规则（user-rules.json）"""
        ...

    def load_template(self, template_id: str) -> RuleSet:
        """加载指定模板"""
        ...

    def list_templates(self) -> list[dict]:
        """列出可用模板：[{"id": "default", "name": "通用采购模板", ...}]"""
        ...

    def load_project_overrides(self, project_id: str) -> RuleSet:
        """加载项目级覆盖规则（存储在项目数据库中，本 Task 仅定义接口签名，Task 2.5 填充）"""
        ...

    # ---- 规则匹配 ----

    def match_column(self, column_name: str, rules: RuleSet, project_rules: RuleSet | None = None) -> MatchResult:
        """
        对单个列名执行规则匹配。
        1. 合并 rules + project_rules
        2. 按优先级排序
        3. 逐条尝试匹配（精确 → 正则 → 模糊）
        4. 调用 resolve_conflict 处理冲突
        """
        ...

    def _match_exact(self, column_name: str, rule: ColumnMappingRule) -> bool:
        """精确匹配：column_name 在 rule.source_keywords 中（不区分大小写，去除前后空格）"""
        ...

    def _match_regex(self, column_name: str, rule: ColumnMappingRule) -> bool:
        """正则匹配：任一 source_keywords 作为正则模式匹配 column_name"""
        ...

    def _match_fuzzy(self, column_name: str, rule: ColumnMappingRule, threshold: int = 80) -> bool:
        """
        模糊匹配：使用 rapidfuzz 计算相似度。
        ⚠️ 首次使用 rapidfuzz API — 必须用 Context7 查文档确认用法。
        """
        # from rapidfuzz import fuzz
        # 对 rule.source_keywords 中每个关键词计算 fuzz.ratio
        # 任一关键词相似度 >= threshold 则认为匹配
        ...

    def resolve_conflict(self, matches: list[tuple[ColumnMappingRule, RuleSource]]) -> MatchResult:
        """
        冲突解决优先级（PRD 3.1.6）：
        1. 项目级 > 全局用户 > 内置模板
        2. 精确 > 正则 > 模糊
        3. 同层级同方式：后创建优先（created_at 更晚的）
        4. 仍有歧义：标记 needs_manual_confirm
        返回 MatchResult，包含最终选择和冲突列表。
        """
        ...

    def test_rule(self, column_name: str, project_rules: RuleSet | None = None) -> MatchResult:
        """最小规则测试能力：输入列名 → 返回映射结果 + 冲突提示"""
        global_rules = self.load_global_rules()
        return self.match_column(column_name, global_rules, project_rules)

    # ---- 规则 CRUD ----

    def add_rule(self, rule_data: dict) -> ColumnMappingRule | ValueNormalizationRule:
        """新增规则到 user-rules.json"""
        ...

    def update_rule(self, rule_id: str, rule_data: dict) -> ColumnMappingRule | ValueNormalizationRule:
        """编辑规则"""
        ...

    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        ...

    def toggle_rule(self, rule_id: str) -> bool:
        """启用/停用规则，返回新状态"""
        ...

    # ---- 导入/导出 ----

    def import_rules(self, imported_rules: RuleSet, strategy: str = "ask") -> dict:
        """
        导入规则。strategy: 'overwrite_all' / 'skip_all' / 'ask'
        返回 {"total": N, "added": N, "conflicts": [...], "skipped": N}
        """
        ...

    def export_rules(self) -> RuleSet:
        """导出全局规则"""
        ...

    def reset_default(self) -> None:
        """恢复默认模板（将 default-template.json 复制为 user-rules.json）"""
        ...

    def apply_template(self, template_id: str) -> None:
        """加载指定模板覆盖当前用户规则"""
        ...

    # ---- 私有方法 ----

    def _read_rule_file(self, filename: str) -> RuleSet:
        """读取规则 JSON 文件"""
        ...

    def _write_rule_file(self, filename: str, rule_set: RuleSet) -> None:
        """
        原子写入规则 JSON 文件。
        必须使用：写临时文件 → fsync → rename
        """
        file_path = self.rules_dir / filename
        tmp_path = file_path.with_suffix(".tmp")
        data = rule_set.model_dump(by_alias=True)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(file_path)

    def _ensure_default_templates(self) -> None:
        """确保内置默认模板存在，首次运行时生成"""
        ...

    def _get_default_template_rules(self) -> RuleSet:
        """通用采购模板：包含 9 个标准字段的默认列名映射规则"""
        ...

    def _get_it_device_template_rules(self) -> RuleSet:
        """IT 设备模板：包含 IT 采购常见列名映射"""
        ...
```

**关键设计点：**

1. **规则文件存储路径**：`app_data/rules/` 下
   - `default-template.json` — 内置通用采购模板（只读，重置时使用）
   - `it-device-template.json` — IT 设备模板（只读）
   - `user-rules.json` — 用户当前生效的规则（可读写）

2. **原子写入**：所有 JSON 文件写操作必须使用临时文件 + fsync + rename

3. **匹配优先级排序**：
   - 第一维：RuleSource（project > global > template）
   - 第二维：MatchMode（exact > regex > fuzzy）
   - 第三维：创建时间（后创建优先）

4. **模糊匹配**：使用 `rapidfuzz.fuzz.ratio`，阈值默认 80。⚠️ **首次使用 rapidfuzz API — 必须用 Context7 查文档确认用法**

5. **默认模板数据**：内置两套模板
   - 通用采购模板：覆盖 PRD 3.1.7 标准字段定义表中所有默认映射关键词
   - IT 设备模板：在通用模板基础上增加 IT 采购常见列名（如"配置"→spec_model、"品牌"等）

6. **`target_field` 校验**：所有映射目标必须在 `STANDARD_FIELDS` 白名单中

## 测试与验收

### fixture 设计

```python
@pytest.fixture
def rules_dir(tmp_path):
    """临时规则目录"""
    d = tmp_path / "rules"
    d.mkdir()
    return d

@pytest.fixture
def engine(rules_dir):
    """RuleEngine 实例"""
    return RuleEngine(rules_dir)
```

### 测试用例清单

```python
# ---- 模板和加载 ----
# test_ensure_default_templates — 首次调用自动生成模板文件
# test_load_global_rules_empty — 无 user-rules.json 时返回空 RuleSet
# test_load_global_rules_with_data — 有规则时正确加载
# test_list_templates — 返回至少 2 个模板

# ---- 精确匹配 ----
# test_match_exact_hit — "单价" 精确命中 unit_price
# test_match_exact_case_insensitive — "Unit Price" 不区分大小写
# test_match_exact_miss — 不存在的列名返回 matched=False

# ---- 模糊匹配 ----
# test_match_fuzzy_hit — "报价含税" 模糊命中 unit_price
# test_match_fuzzy_below_threshold — 相似度不够时不匹配

# ---- 正则匹配 ----
# test_match_regex_hit — 正则模式 ".*税.*单价.*" 匹配

# ---- 冲突解决 ----
# test_resolve_conflict_source_priority — 项目级 > 全局
# test_resolve_conflict_match_mode_priority — 精确 > 模糊
# test_resolve_conflict_created_at — 同级同方式，后创建优先
# test_resolve_conflict_ambiguous — 仍有歧义时标记需人工确认

# ---- CRUD ----
# test_add_rule — 新增规则后可查到
# test_update_rule — 编辑规则后内容更新
# test_delete_rule — 删除后不可查到
# test_toggle_rule — 启用/停用切换

# ---- 导入导出 ----
# test_export_rules — 导出内容与当前规则一致
# test_import_rules_no_conflict — 无冲突时全部导入
# test_import_rules_with_conflict — 有冲突时返回冲突列表
# test_import_overwrite_all — overwrite_all 策略覆盖所有

# ---- 原子写入 ----
# test_atomic_write — 写入后文件内容正确，无 .tmp 残留

# ---- 规则测试 ----
# test_test_rule — 输入列名返回正确映射结果
# test_test_rule_with_conflicts — 有冲突时返回冲突信息
```

**断言清单：**

- `match_column("单价", rules)` → `matched=True, targetField="unit_price"`
- `match_column("不存在的列名", rules)` → `matched=False`
- `resolve_conflict` 按三维优先级正确排序
- 歧义冲突时 `MatchResult` 包含 `conflicts` 列表
- 原子写入后无 `.tmp` 文件残留
- 模板至少包含 PRD 定义的 9 个标准字段映射
- `target_field` 不在白名单中时拒绝

**门禁命令：**

```bash
cd backend
ruff check engines/rule_engine.py tests/test_rule_engine.py
mypy engines/rule_engine.py --ignore-missing-imports
pytest tests/test_rule_engine.py -x -q
```

## 提交

```bash
git add backend/engines/rule_engine.py backend/tests/test_rule_engine.py
git commit -m "Phase 2.2: RuleEngine — 规则加载/匹配/冲突解决/CRUD/导入导出/原子写入"
```
