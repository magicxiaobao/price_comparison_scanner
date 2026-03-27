import { useEffect, useState } from "react";
import type {
  ColumnMappingRule,
  ValueNormalizationRule,
  RuleType,
  MatchMode,
  RuleCreateUpdate,
} from "../../types/rule";
import { useRuleStore } from "../../stores/rule-store";

/** 9 个标准字段 */
const TARGET_FIELDS = [
  { value: "product_name", label: "商品名称" },
  { value: "spec_model", label: "规格型号" },
  { value: "unit", label: "单位" },
  { value: "quantity", label: "数量" },
  { value: "unit_price", label: "单价" },
  { value: "total_price", label: "总价" },
  { value: "tax_rate", label: "税率" },
  { value: "delivery_period", label: "交期" },
  { value: "remark", label: "备注" },
];

interface RuleEditorProps {
  rule: ColumnMappingRule | ValueNormalizationRule | null;
  onClose: () => void;
}

export function RuleEditor({ rule, onClose }: RuleEditorProps) {
  const { upsertRule } = useRuleStore();

  const [ruleType, setRuleType] = useState<RuleType>(rule?.type ?? "column_mapping");
  const [sourceKeywords, setSourceKeywords] = useState("");
  const [targetField, setTargetField] = useState("product_name");
  const [matchMode, setMatchMode] = useState<MatchMode>("exact");
  const [priority, setPriority] = useState(100);
  const [field, setField] = useState("product_name");
  const [patterns, setPatterns] = useState("");
  const [replaceWith, setReplaceWith] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!rule) {
      setRuleType("column_mapping");
      setSourceKeywords("");
      setTargetField("product_name");
      setMatchMode("exact");
      setPriority(100);
      setField("product_name");
      setPatterns("");
      setReplaceWith("");
      return;
    }
    setRuleType(rule.type);
    if (rule.type === "column_mapping") {
      const cm = rule as ColumnMappingRule;
      setSourceKeywords(cm.sourceKeywords.join(", "));
      setTargetField(cm.targetField);
      setMatchMode(cm.matchMode);
      setPriority(cm.priority);
    } else {
      const vn = rule as ValueNormalizationRule;
      setField(vn.field);
      setPatterns(vn.patterns.join(", "));
      setReplaceWith(vn.replaceWith);
    }
  }, [rule]);

  const handleSubmit = async () => {
    setError(null);
    const payload: RuleCreateUpdate = { type: ruleType };

    if (ruleType === "column_mapping") {
      const kws = sourceKeywords
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (kws.length === 0) {
        setError("请输入至少一个关键词");
        return;
      }
      payload.sourceKeywords = kws;
      payload.targetField = targetField;
      payload.matchMode = matchMode;
      payload.priority = priority;
    } else {
      const pts = patterns
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (pts.length === 0) {
        setError("请输入至少一个模式");
        return;
      }
      if (!replaceWith.trim()) {
        setError("替换值不能为空");
        return;
      }
      payload.field = field;
      payload.patterns = pts;
      payload.replaceWith = replaceWith.trim();
    }

    setSubmitting(true);
    try {
      await upsertRule(payload);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-900">
          {rule ? "编辑规则" : "新增规则"}
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {/* 规则类型选择 */}
        {!rule && (
          <div className="mb-4">
            <label className="mb-1 block text-xs font-medium text-gray-700">规则类型</label>
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value as RuleType)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="column_mapping">列名映射</option>
              <option value="value_normalization">值标准化</option>
            </select>
          </div>
        )}

        {ruleType === "column_mapping" ? (
          <>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">
                关键词（逗号分隔）
              </label>
              <input
                type="text"
                value={sourceKeywords}
                onChange={(e) => setSourceKeywords(e.target.value)}
                placeholder="如：单价, 报价, Unit Price"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">目标字段</label>
              <select
                value={targetField}
                onChange={(e) => setTargetField(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {TARGET_FIELDS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label} ({f.value})
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">匹配方式</label>
              <select
                value={matchMode}
                onChange={(e) => setMatchMode(e.target.value as MatchMode)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="exact">精确匹配</option>
                <option value="fuzzy">模糊匹配</option>
                <option value="regex">正则匹配</option>
              </select>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">优先级</label>
              <input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </>
        ) : (
          <>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">适用字段</label>
              <select
                value={field}
                onChange={(e) => setField(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {TARGET_FIELDS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label} ({f.value})
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">
                模式列表（逗号分隔）
              </label>
              <input
                type="text"
                value={patterns}
                onChange={(e) => setPatterns(e.target.value)}
                placeholder="如：lenovo, 联想"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-700">替换为</label>
              <input
                type="text"
                value={replaceWith}
                onChange={(e) => setReplaceWith(e.target.value)}
                placeholder="如：联想"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </>
        )}

        {error && <p className="mb-2 text-xs text-red-600">{error}</p>}
      </div>

      <div className="flex gap-3 border-t border-gray-200 px-4 py-3">
        <button
          onClick={onClose}
          disabled={submitting}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          取消
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="flex-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "保存中..." : "保存"}
        </button>
      </div>
    </div>
  );
}
