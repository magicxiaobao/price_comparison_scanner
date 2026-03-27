import { useState } from "react";
import type { ColumnMappingRule, ValueNormalizationRule } from "../../types/rule";
import { useRuleStore } from "../../stores/rule-store";

interface RuleListProps {
  onSelectRule: (rule: ColumnMappingRule | ValueNormalizationRule) => void;
  onNewRule: () => void;
}

const MATCH_MODE_LABELS: Record<string, string> = {
  exact: "精确",
  fuzzy: "模糊",
  regex: "正则",
};

export function RuleList({ onSelectRule, onNewRule }: RuleListProps) {
  const { rules, isLoading, error, toggleRule, deleteRule, clearError } = useRuleStore();
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  if (isLoading && !rules) {
    return <p className="p-4 text-sm text-gray-500">加载规则中...</p>;
  }

  if (error) {
    return (
      <div className="p-4">
        <p className="text-sm text-red-600">{error}</p>
        <button onClick={clearError} className="mt-2 text-xs text-blue-600 hover:underline">
          清除错误
        </button>
      </div>
    );
  }

  if (!rules) {
    return <p className="p-4 text-sm text-gray-500">无规则数据</p>;
  }

  const handleDelete = async (ruleId: string) => {
    await deleteRule(ruleId);
    setDeleteConfirm(null);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        {/* 列名映射规则 */}
        <div className="border-b border-gray-200 px-4 py-2">
          <h3 className="text-sm font-semibold text-gray-700">
            列名映射规则 ({rules.columnMappingRules.length})
          </h3>
        </div>
        {rules.columnMappingRules.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400">暂无列名映射规则</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {rules.columnMappingRules.map((rule) => (
              <li
                key={rule.id}
                className="flex cursor-pointer items-center gap-2 px-4 py-3 hover:bg-gray-50"
                onClick={() => onSelectRule(rule)}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleRule(rule.id);
                  }}
                  className={`h-4 w-4 shrink-0 rounded-full border-2 ${
                    rule.enabled
                      ? "border-green-500 bg-green-500"
                      : "border-gray-300 bg-white"
                  }`}
                  title={rule.enabled ? "点击停用" : "点击启用"}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">
                    {rule.sourceKeywords.join(", ")} &rarr; {rule.targetField}
                  </p>
                  <p className="text-xs text-gray-500">
                    {MATCH_MODE_LABELS[rule.matchMode] ?? rule.matchMode} | 优先级 {rule.priority}
                  </p>
                </div>
                {deleteConfirm === rule.id ? (
                  <div className="flex shrink-0 gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(rule.id);
                      }}
                      className="rounded bg-red-600 px-2 py-0.5 text-xs text-white"
                    >
                      确认
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirm(null);
                      }}
                      className="rounded border px-2 py-0.5 text-xs text-gray-600"
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(rule.id);
                    }}
                    className="shrink-0 text-xs text-red-500 hover:text-red-700"
                    title="删除"
                  >
                    删除
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* 值标准化规则 */}
        <div className="border-b border-t border-gray-200 px-4 py-2">
          <h3 className="text-sm font-semibold text-gray-700">
            值标准化规则 ({rules.valueNormalizationRules.length})
          </h3>
        </div>
        {rules.valueNormalizationRules.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400">暂无值标准化规则</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {rules.valueNormalizationRules.map((rule) => (
              <li
                key={rule.id}
                className="flex cursor-pointer items-center gap-2 px-4 py-3 hover:bg-gray-50"
                onClick={() => onSelectRule(rule)}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">
                    {rule.field}: {rule.patterns.join(", ")} &rarr; {rule.replaceWith}
                  </p>
                </div>
                {deleteConfirm === rule.id ? (
                  <div className="flex shrink-0 gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(rule.id);
                      }}
                      className="rounded bg-red-600 px-2 py-0.5 text-xs text-white"
                    >
                      确认
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirm(null);
                      }}
                      className="rounded border px-2 py-0.5 text-xs text-gray-600"
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(rule.id);
                    }}
                    className="shrink-0 text-xs text-red-500 hover:text-red-700"
                    title="删除"
                  >
                    删除
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 底部操作按钮 */}
      <div className="border-t border-gray-200 px-4 py-3">
        <button
          onClick={onNewRule}
          className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          新增规则
        </button>
      </div>
    </div>
  );
}
