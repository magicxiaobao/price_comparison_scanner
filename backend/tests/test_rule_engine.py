"""Task 2.2: RuleEngine 单元测试"""
import json

import pytest

from engines.rule_engine import STANDARD_FIELDS, RuleEngine
from models.rule import (
    ColumnMappingRule,
    MatchMode,
    RuleSet,
    RuleSource,
    ValueNormalizationRule,
)


@pytest.fixture
def rules_dir(tmp_path):  # type: ignore[no-untyped-def]
    """临时规则目录"""
    d = tmp_path / "rules"
    d.mkdir()
    return d


@pytest.fixture
def engine(rules_dir):  # type: ignore[no-untyped-def]
    """RuleEngine 实例"""
    return RuleEngine(rules_dir)


def _make_rule(
    rule_id: str = "r1",
    keywords: list[str] | None = None,
    target: str = "unit_price",
    mode: MatchMode = MatchMode.exact,
    priority: int = 100,
    created_at: str = "2026-01-01T00:00:00Z",
) -> ColumnMappingRule:
    return ColumnMappingRule(
        id=rule_id,
        source_keywords=keywords or ["单价"],
        target_field=target,
        match_mode=mode,
        priority=priority,
        created_at=created_at,
    )


# ── 模板和加载 ──


class TestTemplatesAndLoading:
    def test_ensure_default_templates(self, engine: RuleEngine) -> None:
        engine._ensure_default_templates()
        assert (engine.rules_dir / "default-template.json").exists()
        assert (engine.rules_dir / "it-device-template.json").exists()

    def test_load_global_rules_empty(self, engine: RuleEngine) -> None:
        rs = engine.load_global_rules()
        assert isinstance(rs, RuleSet)
        assert rs.column_mapping_rules == []

    def test_load_global_rules_with_data(self, engine: RuleEngine) -> None:
        rule = _make_rule()
        rs = RuleSet(column_mapping_rules=[rule])
        engine._write_rule_file("user-rules.json", rs)
        loaded = engine.load_global_rules()
        assert len(loaded.column_mapping_rules) == 1
        assert loaded.column_mapping_rules[0].target_field == "unit_price"

    def test_list_templates(self, engine: RuleEngine) -> None:
        engine._ensure_default_templates()
        templates = engine.list_templates()
        assert len(templates) >= 2
        ids = [t["id"] for t in templates]
        assert "default" in ids
        assert "it-device" in ids

    def test_load_template(self, engine: RuleEngine) -> None:
        engine._ensure_default_templates()
        rs = engine.load_template("default")
        assert len(rs.column_mapping_rules) >= 9  # 至少覆盖 9 个标准字段

    def test_default_template_covers_all_fields(self, engine: RuleEngine) -> None:
        engine._ensure_default_templates()
        rs = engine.load_template("default")
        covered = {r.target_field for r in rs.column_mapping_rules}
        for f in STANDARD_FIELDS:
            assert f in covered, f"标准字段 {f} 未被默认模板覆盖"


# ── 精确匹配 ──


class TestExactMatch:
    def test_match_exact_hit(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["单价", "报价"])
        assert engine._match_exact("单价", rule) is True

    def test_match_exact_case_insensitive(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["Unit Price"])
        assert engine._match_exact("unit price", rule) is True

    def test_match_exact_strip_whitespace(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["单价"])
        assert engine._match_exact("  单价  ", rule) is True

    def test_match_exact_miss(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["单价"])
        assert engine._match_exact("不存在的列名", rule) is False


# ── 模糊匹配 ──


class TestFuzzyMatch:
    def test_match_fuzzy_hit(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["报价"], mode=MatchMode.fuzzy)
        # "报价含税" vs "报价" — ratio ~67%, but we test with lower threshold
        assert engine._match_fuzzy("报价含税", rule, threshold=60) is True

    def test_match_fuzzy_below_threshold(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["报价"], mode=MatchMode.fuzzy)
        assert engine._match_fuzzy("完全不相关", rule, threshold=80) is False

    def test_match_fuzzy_high_similarity(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["含税单价"], mode=MatchMode.fuzzy)
        assert engine._match_fuzzy("含税单价（元）", rule, threshold=70) is True


# ── 正则匹配 ──


class TestRegexMatch:
    def test_match_regex_hit(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=[".*税.*单价.*"], mode=MatchMode.regex)
        assert engine._match_regex("含税单价", rule) is True

    def test_match_regex_miss(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=[".*税.*单价.*"], mode=MatchMode.regex)
        assert engine._match_regex("品名", rule) is False

    def test_match_regex_invalid_pattern(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["[invalid"], mode=MatchMode.regex)
        assert engine._match_regex("test", rule) is False


# ── match_column 综合 ──


class TestMatchColumn:
    def test_match_column_hit(self, engine: RuleEngine) -> None:
        rules = RuleSet(column_mapping_rules=[
            _make_rule(keywords=["单价", "报价"], target="unit_price"),
        ])
        result = engine.match_column("单价", rules)
        assert result.matched is True
        assert result.target_field == "unit_price"

    def test_match_column_miss(self, engine: RuleEngine) -> None:
        rules = RuleSet(column_mapping_rules=[
            _make_rule(keywords=["单价"], target="unit_price"),
        ])
        result = engine.match_column("不存在的列名", rules)
        assert result.matched is False

    def test_match_column_disabled_rule_skipped(self, engine: RuleEngine) -> None:
        rule = _make_rule(keywords=["单价"], target="unit_price")
        rule.enabled = False
        rules = RuleSet(column_mapping_rules=[rule])
        result = engine.match_column("单价", rules)
        assert result.matched is False

    def test_match_column_with_project_override(self, engine: RuleEngine) -> None:
        global_rules = RuleSet(column_mapping_rules=[
            _make_rule("g1", keywords=["单价"], target="unit_price"),
        ])
        project_rules = RuleSet(column_mapping_rules=[
            _make_rule("p1", keywords=["单价"], target="total_price"),
        ])
        result = engine.match_column("单价", global_rules, project_rules)
        # 项目级覆盖全局
        assert result.target_field == "total_price"


# ── 冲突解决 ──


class TestConflictResolution:
    def test_resolve_conflict_source_priority(self, engine: RuleEngine) -> None:
        global_rule = _make_rule("g1", target="unit_price")
        project_rule = _make_rule("p1", target="total_price")
        matches = [
            (global_rule, RuleSource.global_user),
            (project_rule, RuleSource.project),
        ]
        result = engine.resolve_conflict(matches)
        assert result.target_field == "total_price"

    def test_resolve_conflict_match_mode_priority(self, engine: RuleEngine) -> None:
        exact_rule = _make_rule("r1", target="unit_price", mode=MatchMode.exact)
        fuzzy_rule = _make_rule("r2", target="total_price", mode=MatchMode.fuzzy)
        matches = [
            (fuzzy_rule, RuleSource.global_user),
            (exact_rule, RuleSource.global_user),
        ]
        result = engine.resolve_conflict(matches)
        assert result.target_field == "unit_price"

    def test_resolve_conflict_created_at(self, engine: RuleEngine) -> None:
        old_rule = _make_rule("r1", target="unit_price", created_at="2026-01-01T00:00:00Z")
        new_rule = _make_rule("r2", target="total_price", created_at="2026-03-01T00:00:00Z")
        matches = [
            (old_rule, RuleSource.global_user),
            (new_rule, RuleSource.global_user),
        ]
        result = engine.resolve_conflict(matches)
        assert result.target_field == "total_price"

    def test_resolve_conflict_ambiguous(self, engine: RuleEngine) -> None:
        r1 = _make_rule("r1", target="unit_price", created_at="2026-01-01T00:00:00Z")
        r2 = _make_rule("r2", target="total_price", created_at="2026-01-01T00:00:00Z")
        matches = [
            (r1, RuleSource.global_user),
            (r2, RuleSource.global_user),
        ]
        result = engine.resolve_conflict(matches)
        assert len(result.conflicts) >= 2
        assert result.resolution is not None


# ── CRUD ──


class TestCRUD:
    def test_add_rule(self, engine: RuleEngine) -> None:
        rule = engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
            "matchMode": "exact",
        })
        assert isinstance(rule, ColumnMappingRule)
        loaded = engine.load_global_rules()
        assert len(loaded.column_mapping_rules) == 1

    def test_add_value_normalization_rule(self, engine: RuleEngine) -> None:
        rule = engine.add_rule({
            "type": "value_normalization",
            "field": "unit",
            "patterns": ["个", "只"],
            "replaceWith": "个",
        })
        assert isinstance(rule, ValueNormalizationRule)

    def test_add_rule_invalid_target(self, engine: RuleEngine) -> None:
        with pytest.raises(ValueError, match="STANDARD_FIELDS"):
            engine.add_rule({
                "type": "column_mapping",
                "sourceKeywords": ["xxx"],
                "targetField": "invalid_field",
            })

    def test_update_rule(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
        })
        rules = engine.load_global_rules()
        rule_id = rules.column_mapping_rules[0].id
        updated = engine.update_rule(rule_id, {
            "type": "column_mapping",
            "sourceKeywords": ["单价", "报价"],
            "targetField": "unit_price",
        })
        assert isinstance(updated, ColumnMappingRule)
        assert len(updated.source_keywords) == 2

    def test_delete_rule(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
        })
        rules = engine.load_global_rules()
        rule_id = rules.column_mapping_rules[0].id
        assert engine.delete_rule(rule_id) is True
        assert len(engine.load_global_rules().column_mapping_rules) == 0

    def test_delete_rule_not_found(self, engine: RuleEngine) -> None:
        assert engine.delete_rule("nonexistent") is False

    def test_toggle_rule(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
        })
        rules = engine.load_global_rules()
        rule_id = rules.column_mapping_rules[0].id
        new_state = engine.toggle_rule(rule_id)
        assert new_state is False  # was True by default
        new_state = engine.toggle_rule(rule_id)
        assert new_state is True


# ── 导入导出 ──


class TestImportExport:
    def test_export_rules(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
        })
        exported = engine.export_rules()
        assert len(exported.column_mapping_rules) == 1

    def test_import_rules_no_conflict(self, engine: RuleEngine) -> None:
        imported = RuleSet(column_mapping_rules=[
            _make_rule("imp1", keywords=["品名"], target="product_name"),
        ])
        result = engine.import_rules(imported, strategy="skip_all")
        assert result["added"] == 1
        assert result["conflicts"] == 0

    def test_import_rules_with_conflict(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
        })
        imported = RuleSet(column_mapping_rules=[
            _make_rule("imp1", keywords=["单价"], target="total_price"),
        ])
        result = engine.import_rules(imported, strategy="skip_all")
        assert result["skipped"] >= 1

    def test_import_overwrite_all(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价"],
            "targetField": "unit_price",
        })
        imported = RuleSet(column_mapping_rules=[
            _make_rule("imp1", keywords=["单价"], target="total_price"),
        ])
        result = engine.import_rules(imported, strategy="overwrite_all")
        assert result["added"] >= 1
        rules = engine.load_global_rules()
        targets = [r.target_field for r in rules.column_mapping_rules if "单价" in r.source_keywords]
        assert "total_price" in targets


# ── 原子写入 ──


class TestAtomicWrite:
    def test_atomic_write(self, engine: RuleEngine) -> None:
        rs = RuleSet(column_mapping_rules=[_make_rule()])
        engine._write_rule_file("test.json", rs)
        assert (engine.rules_dir / "test.json").exists()
        assert not (engine.rules_dir / "test.tmp").exists()
        with open(engine.rules_dir / "test.json", encoding="utf-8") as f:
            data = json.load(f)
        assert "columnMappingRules" in data


# ── 规则测试 ──


class TestRuleTest:
    def test_test_rule(self, engine: RuleEngine) -> None:
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["单价", "报价"],
            "targetField": "unit_price",
        })
        result = engine.test_rule("单价")
        assert result.matched is True
        assert result.target_field == "unit_price"

    def test_test_rule_no_match(self, engine: RuleEngine) -> None:
        result = engine.test_rule("不存在的列名")
        assert result.matched is False


# ── 模板操作 ──


class TestTemplateOperations:
    def test_reset_default(self, engine: RuleEngine) -> None:
        engine._ensure_default_templates()
        engine.add_rule({
            "type": "column_mapping",
            "sourceKeywords": ["自定义"],
            "targetField": "remark",
        })
        engine.reset_default()
        rules = engine.load_global_rules()
        custom = [r for r in rules.column_mapping_rules if "自定义" in r.source_keywords]
        assert len(custom) == 0

    def test_apply_template(self, engine: RuleEngine) -> None:
        engine._ensure_default_templates()
        engine.apply_template("it-device")
        rules = engine.load_global_rules()
        assert len(rules.column_mapping_rules) > 0
