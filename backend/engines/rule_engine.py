from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rapidfuzz import fuzz

from models.rule import (
    ColumnMappingRule,
    MatchMode,
    MatchResult,
    RuleSet,
    RuleSource,
    RuleType,
    ValueNormalizationRule,
)

# 标准字段白名单
STANDARD_FIELDS = [
    "product_name",
    "spec_model",
    "unit",
    "quantity",
    "unit_price",
    "total_price",
    "tax_rate",
    "delivery_period",
    "remark",
]

# RuleSource 排序权重（越大越优先）
_SOURCE_PRIORITY: dict[RuleSource, int] = {
    RuleSource.project: 3,
    RuleSource.global_user: 2,
    RuleSource.template: 1,
}

# MatchMode 排序权重
_MODE_PRIORITY: dict[MatchMode, int] = {
    MatchMode.exact: 3,
    MatchMode.regex: 2,
    MatchMode.fuzzy: 1,
}


class RuleEngine:
    """
    全局规则 + 项目覆盖，含冲突解决。
    规则存储在 app_data/rules/ 下的 JSON 文件。
    """

    def __init__(self, rules_dir: Path) -> None:
        self.rules_dir = rules_dir
        self.rules_dir.mkdir(parents=True, exist_ok=True)

    # ── 规则加载 ──

    def load_global_rules(self) -> RuleSet:
        """加载用户自定义规则（user-rules.json）"""
        path = self.rules_dir / "user-rules.json"
        if not path.exists():
            return RuleSet()
        return self._read_rule_file("user-rules.json")

    def load_template(self, template_id: str) -> RuleSet:
        """加载指定模板"""
        filename = f"{template_id}-template.json"
        path = self.rules_dir / filename
        if not path.exists():
            self._ensure_default_templates()
        if not path.exists():
            raise FileNotFoundError(f"模板不存在: {template_id}")
        return self._read_rule_file(filename)

    def list_templates(self) -> list[dict]:
        """列出可用模板"""
        self._ensure_default_templates()
        templates: list[dict] = []
        for f in sorted(self.rules_dir.glob("*-template.json")):
            rs = self._read_rule_file(f.name)
            tid = f.stem.replace("-template", "")
            name_map = {"default": "通用采购模板", "it-device": "IT 设备模板"}
            desc_map = {
                "default": "覆盖 9 个标准字段的默认列名映射规则",
                "it-device": "在通用模板基础上增加 IT 采购常见列名映射",
            }
            total = len(rs.column_mapping_rules) + len(rs.value_normalization_rules)
            templates.append({
                "id": tid,
                "name": name_map.get(tid, tid),
                "description": desc_map.get(tid, ""),
                "ruleCount": total,
            })
        return templates

    def load_project_overrides(self, project_id: str) -> RuleSet:
        """加载项目级覆盖规则（Task 2.5 填充实现）"""
        return RuleSet()

    # ── 规则匹配 ──

    def match_column(
        self,
        column_name: str,
        rules: RuleSet,
        project_rules: RuleSet | None = None,
    ) -> MatchResult:
        """
        对单个列名执行规则匹配。
        合并 rules + project_rules，按优先级排序，逐条尝试匹配。
        """
        candidates: list[tuple[ColumnMappingRule, RuleSource]] = []

        for rule in rules.column_mapping_rules:
            if not rule.enabled:
                continue
            if self._try_match(column_name, rule):
                candidates.append((rule, RuleSource.global_user))

        if project_rules:
            for rule in project_rules.column_mapping_rules:
                if not rule.enabled:
                    continue
                if self._try_match(column_name, rule):
                    candidates.append((rule, RuleSource.project))

        if not candidates:
            return MatchResult(matched=False)

        if len(candidates) == 1:
            rule, _src = candidates[0]
            return MatchResult(
                matched=True,
                target_field=rule.target_field,
                matched_rule=rule,
            )

        return self.resolve_conflict(candidates)

    def _try_match(self, column_name: str, rule: ColumnMappingRule) -> bool:
        if rule.match_mode == MatchMode.exact:
            return self._match_exact(column_name, rule)
        if rule.match_mode == MatchMode.regex:
            return self._match_regex(column_name, rule)
        if rule.match_mode == MatchMode.fuzzy:
            return self._match_fuzzy(column_name, rule)
        return False

    def _match_exact(self, column_name: str, rule: ColumnMappingRule) -> bool:
        """精确匹配：不区分大小写，去除前后空格"""
        normalized = column_name.strip().lower()
        return any(kw.strip().lower() == normalized for kw in rule.source_keywords)

    def _match_regex(self, column_name: str, rule: ColumnMappingRule) -> bool:
        """正则匹配：任一 source_keywords 作为正则模式匹配 column_name"""
        for pattern in rule.source_keywords:
            try:
                if re.fullmatch(pattern, column_name, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    def _match_fuzzy(
        self, column_name: str, rule: ColumnMappingRule, threshold: int = 80
    ) -> bool:
        """模糊匹配：使用 rapidfuzz.fuzz.ratio，阈值默认 80"""
        for kw in rule.source_keywords:
            score = fuzz.ratio(column_name.strip(), kw.strip())
            if score >= threshold:
                return True
        return False

    def resolve_conflict(
        self, matches: list[tuple[ColumnMappingRule, RuleSource]]
    ) -> MatchResult:
        """
        冲突解决优先级：
        1. 项目级 > 全局用户 > 内置模板
        2. 精确 > 正则 > 模糊
        3. 同层级同方式：后创建优先
        4. 仍有歧义：标记 needs_manual_confirm
        """

        def sort_key(item: tuple[ColumnMappingRule, RuleSource]) -> tuple[int, int, str]:
            rule, source = item
            return (
                _SOURCE_PRIORITY.get(source, 0),
                _MODE_PRIORITY.get(rule.match_mode, 0),
                rule.created_at,
            )

        sorted_matches = sorted(matches, key=sort_key, reverse=True)
        best_rule, best_source = sorted_matches[0]

        # Check if top two are truly ambiguous (same source, same mode, same created_at)
        all_rules = [r for r, _ in matches]
        if len(sorted_matches) >= 2:
            second_rule, second_source = sorted_matches[1]
            best_key = sort_key(sorted_matches[0])
            second_key = sort_key(sorted_matches[1])
            if best_key == second_key:
                return MatchResult(
                    matched=True,
                    target_field=best_rule.target_field,
                    matched_rule=best_rule,
                    conflicts=all_rules,
                    resolution="命中多条规则，需人工确认",
                )

        return MatchResult(
            matched=True,
            target_field=best_rule.target_field,
            matched_rule=best_rule,
            conflicts=all_rules if len(all_rules) > 1 else [],
            resolution=f"按优先级选择: {best_source.value} > {best_rule.match_mode.value}"
            if len(all_rules) > 1
            else None,
        )

    def test_rule(
        self, column_name: str, project_rules: RuleSet | None = None
    ) -> MatchResult:
        """最小规则测试能力：输入列名 → 返回映射结果 + 冲突提示"""
        global_rules = self.load_global_rules()
        return self.match_column(column_name, global_rules, project_rules)

    # ── 规则 CRUD ──

    def add_rule(
        self, rule_data: dict,
    ) -> ColumnMappingRule | ValueNormalizationRule:
        """新增规则到 user-rules.json"""
        rule_type = RuleType(rule_data.get("type", "column_mapping"))

        if rule_type == RuleType.column_mapping:
            target = rule_data.get("targetField") or rule_data.get("target_field")
            if target and target not in STANDARD_FIELDS:
                raise ValueError(
                    f"target_field '{target}' 不在 STANDARD_FIELDS 白名单中"
                )
            now = datetime.now(UTC).isoformat()
            rule = ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=rule_data.get("sourceKeywords") or rule_data.get("source_keywords", []),
                target_field=target or "",
                match_mode=MatchMode(rule_data.get("matchMode", rule_data.get("match_mode", "exact"))),
                priority=rule_data.get("priority", 100),
                created_at=now,
            )
            rs = self.load_global_rules()
            rs.column_mapping_rules.append(rule)
            rs.last_updated = now
            self._write_rule_file("user-rules.json", rs)
            return rule

        # value_normalization
        now = datetime.now(UTC).isoformat()
        rule_vn = ValueNormalizationRule(
            id=str(uuid.uuid4()),
            field=rule_data.get("field", ""),
            patterns=rule_data.get("patterns", []),
            replace_with=rule_data.get("replaceWith") or rule_data.get("replace_with", ""),
            created_at=now,
        )
        rs = self.load_global_rules()
        rs.value_normalization_rules.append(rule_vn)
        rs.last_updated = now
        self._write_rule_file("user-rules.json", rs)
        return rule_vn

    def update_rule(
        self, rule_id: str, rule_data: dict,
    ) -> ColumnMappingRule | ValueNormalizationRule:
        """编辑规则"""
        rs = self.load_global_rules()
        rule_type = RuleType(rule_data.get("type", "column_mapping"))

        if rule_type == RuleType.column_mapping:
            target = rule_data.get("targetField") or rule_data.get("target_field")
            if target and target not in STANDARD_FIELDS:
                raise ValueError(
                    f"target_field '{target}' 不在 STANDARD_FIELDS 白名单中"
                )
            for i, r in enumerate(rs.column_mapping_rules):
                if r.id == rule_id:
                    updated = ColumnMappingRule(
                        id=rule_id,
                        enabled=rule_data.get("enabled", r.enabled),
                        source_keywords=rule_data.get("sourceKeywords") or rule_data.get("source_keywords", r.source_keywords),
                        target_field=target or r.target_field,
                        match_mode=MatchMode(rule_data.get("matchMode", rule_data.get("match_mode", r.match_mode.value))),
                        priority=rule_data.get("priority", r.priority),
                        created_at=r.created_at,
                    )
                    rs.column_mapping_rules[i] = updated
                    rs.last_updated = datetime.now(UTC).isoformat()
                    self._write_rule_file("user-rules.json", rs)
                    return updated

        if rule_type == RuleType.value_normalization:
            for i, r in enumerate(rs.value_normalization_rules):
                if r.id == rule_id:
                    updated_vn = ValueNormalizationRule(
                        id=rule_id,
                        field=rule_data.get("field", r.field),
                        patterns=rule_data.get("patterns", r.patterns),
                        replace_with=rule_data.get("replaceWith") or rule_data.get("replace_with", r.replace_with),
                        created_at=r.created_at,
                    )
                    rs.value_normalization_rules[i] = updated_vn
                    rs.last_updated = datetime.now(UTC).isoformat()
                    self._write_rule_file("user-rules.json", rs)
                    return updated_vn

        raise ValueError(f"规则 {rule_id} 不存在")

    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        rs = self.load_global_rules()
        original_cm = len(rs.column_mapping_rules)
        original_vn = len(rs.value_normalization_rules)
        rs.column_mapping_rules = [r for r in rs.column_mapping_rules if r.id != rule_id]
        rs.value_normalization_rules = [r for r in rs.value_normalization_rules if r.id != rule_id]
        deleted = (
            len(rs.column_mapping_rules) < original_cm
            or len(rs.value_normalization_rules) < original_vn
        )
        if deleted:
            rs.last_updated = datetime.now(UTC).isoformat()
            self._write_rule_file("user-rules.json", rs)
        return deleted

    def toggle_rule(self, rule_id: str) -> bool:
        """启用/停用规则，返回新状态"""
        rs = self.load_global_rules()
        for rule in rs.column_mapping_rules:
            if rule.id == rule_id:
                rule.enabled = not rule.enabled
                rs.last_updated = datetime.now(UTC).isoformat()
                self._write_rule_file("user-rules.json", rs)
                return rule.enabled
        raise ValueError(f"规则 {rule_id} 不存在")

    # ── 导入/导出 ──

    def import_rules(self, imported_rules: RuleSet, strategy: str = "ask") -> dict:
        """
        导入规则。strategy: 'overwrite_all' / 'skip_all' / 'ask'
        """
        current = self.load_global_rules()
        existing_keywords: dict[str, str] = {}
        for r in current.column_mapping_rules:
            for kw in r.source_keywords:
                existing_keywords[kw.lower()] = r.id

        added = 0
        conflicts = 0
        skipped = 0
        total = len(imported_rules.column_mapping_rules) + len(imported_rules.value_normalization_rules)

        for rule in imported_rules.column_mapping_rules:
            has_conflict = any(
                kw.lower() in existing_keywords for kw in rule.source_keywords
            )
            if has_conflict:
                if strategy == "overwrite_all":
                    for kw in rule.source_keywords:
                        old_id = existing_keywords.get(kw.lower())
                        if old_id:
                            current.column_mapping_rules = [
                                r for r in current.column_mapping_rules if r.id != old_id
                            ]
                    current.column_mapping_rules.append(rule)
                    for kw in rule.source_keywords:
                        existing_keywords[kw.lower()] = rule.id
                    added += 1
                elif strategy == "skip_all":
                    skipped += 1
                else:
                    conflicts += 1
            else:
                current.column_mapping_rules.append(rule)
                for kw in rule.source_keywords:
                    existing_keywords[kw.lower()] = rule.id
                added += 1

        for rule in imported_rules.value_normalization_rules:
            current.value_normalization_rules.append(rule)
            added += 1

        current.last_updated = datetime.now(UTC).isoformat()
        self._write_rule_file("user-rules.json", current)

        return {"total": total, "added": added, "conflicts": conflicts, "skipped": skipped}

    def export_rules(self) -> RuleSet:
        """导出全局规则"""
        return self.load_global_rules()

    def reset_default(self) -> None:
        """恢复默认模板"""
        self._ensure_default_templates()
        default_rs = self._read_rule_file("default-template.json")
        default_rs.last_updated = datetime.now(UTC).isoformat()
        self._write_rule_file("user-rules.json", default_rs)

    def apply_template(self, template_id: str) -> None:
        """加载指定模板覆盖当前用户规则"""
        rs = self.load_template(template_id)
        rs.last_updated = datetime.now(UTC).isoformat()
        self._write_rule_file("user-rules.json", rs)

    # ── 私有方法 ──

    def _read_rule_file(self, filename: str) -> RuleSet:
        """读取规则 JSON 文件"""
        path = self.rules_dir / filename
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return RuleSet(**data)

    def _write_rule_file(self, filename: str, rule_set: RuleSet) -> None:
        """原子写入规则 JSON 文件"""
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
        """确保内置默认模板存在"""
        if not (self.rules_dir / "default-template.json").exists():
            self._write_rule_file(
                "default-template.json", self._get_default_template_rules()
            )
        if not (self.rules_dir / "it-device-template.json").exists():
            self._write_rule_file(
                "it-device-template.json", self._get_it_device_template_rules()
            )

    def _get_default_template_rules(self) -> RuleSet:
        """通用采购模板：覆盖 PRD 3.1.7 标准字段定义表中所有默认映射关键词"""
        now = datetime.now(UTC).isoformat()
        rules = [
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["品名", "名称", "产品名称", "物资名称", "项目名称", "商品名称"],
                target_field="product_name",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["规格", "型号", "规格型号", "配置", "参数"],
                target_field="spec_model",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["单位", "计量单位"],
                target_field="unit",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["数量", "采购数量", "需求数量"],
                target_field="quantity",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["单价", "报价", "含税单价", "不含税单价", "价格"],
                target_field="unit_price",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["总价", "金额", "合计", "小计"],
                target_field="total_price",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["税率", "增值税率", "税点"],
                target_field="tax_rate",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["交期", "交货期", "交货周期", "供货周期", "货期"],
                target_field="delivery_period",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["备注", "说明", "附注"],
                target_field="remark",
                match_mode=MatchMode.exact,
                created_at=now,
            ),
        ]
        return RuleSet(
            version="1.0",
            last_updated=now,
            column_mapping_rules=rules,
        )

    def _get_it_device_template_rules(self) -> RuleSet:
        """IT 设备模板：在通用模板基础上增加 IT 采购常见列名"""
        base = self._get_default_template_rules()
        now = datetime.now(UTC).isoformat()
        it_rules = [
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["设备名称", "产品型号", "设备型号"],
                target_field="product_name",
                match_mode=MatchMode.exact,
                priority=90,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["配置", "硬件配置", "技术参数", "技术规格"],
                target_field="spec_model",
                match_mode=MatchMode.exact,
                priority=90,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["台", "套", "件"],
                target_field="unit",
                match_mode=MatchMode.exact,
                priority=90,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["到货周期", "供货期限", "交付周期"],
                target_field="delivery_period",
                match_mode=MatchMode.exact,
                priority=90,
                created_at=now,
            ),
            ColumnMappingRule(
                id=str(uuid.uuid4()),
                source_keywords=["品牌", "厂商", "制造商"],
                target_field="remark",
                match_mode=MatchMode.exact,
                priority=80,
                created_at=now,
            ),
        ]
        base.column_mapping_rules.extend(it_rules)
        base.last_updated = now
        return base
