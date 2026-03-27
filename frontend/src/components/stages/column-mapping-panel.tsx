import { useState } from "react";
import type { ColumnMappingInfo, StandardFieldKey } from "../../types/standardization";
import { STANDARD_FIELD_LABELS } from "../../types/standardization";

interface ColumnMappingPanelProps {
  mappings: ColumnMappingInfo[];
  onMappingChange?: (originalColumn: string, targetField: string) => void;
}

const STATUS_STYLES: Record<ColumnMappingInfo["status"], { label: string; className: string }> = {
  confirmed: { label: "已确认", className: "bg-green-100 text-green-800" },
  pending: { label: "待确认", className: "bg-yellow-100 text-yellow-800" },
  unmapped: { label: "未映射", className: "bg-gray-100 text-gray-600" },
  conflict: { label: "冲突", className: "bg-red-100 text-red-800" },
};

const TARGET_FIELD_OPTIONS = Object.entries(STANDARD_FIELD_LABELS).map(([key, label]) => ({
  value: key,
  label,
}));

export function ColumnMappingPanel({ mappings, onMappingChange }: ColumnMappingPanelProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (mappings.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">
        暂无列名映射信息，请先执行标准化。
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <div className="border-b border-gray-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-700">列名映射</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs text-gray-500">
              <th className="px-4 py-2">原始列名</th>
              <th className="px-4 py-2">标准字段</th>
              <th className="px-4 py-2">命中规则</th>
              <th className="px-4 py-2">状态</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => {
              const statusInfo = STATUS_STYLES[m.status];
              const needsManualSelect = m.status === "unmapped" || m.status === "conflict";

              return (
                <tr
                  key={m.originalColumn}
                  className="border-b border-gray-50 hover:bg-gray-50"
                >
                  <td className="px-4 py-2 font-mono text-xs">{m.originalColumn}</td>
                  <td className="px-4 py-2">
                    {needsManualSelect ? (
                      <select
                        className="rounded border border-gray-300 px-2 py-1 text-xs"
                        value={m.targetField ?? ""}
                        onChange={(e) =>
                          onMappingChange?.(m.originalColumn, e.target.value)
                        }
                      >
                        <option value="">-- 选择字段 --</option>
                        {TARGET_FIELD_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-gray-700">
                        {m.targetField
                          ? STANDARD_FIELD_LABELS[m.targetField as StandardFieldKey] ??
                            m.targetField
                          : "-"}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {m.matchedRule ? (
                      <button
                        type="button"
                        className="text-blue-600 underline-offset-2 hover:underline"
                        onClick={() =>
                          setExpandedRow(
                            expandedRow === m.originalColumn ? null : m.originalColumn,
                          )
                        }
                      >
                        {m.matchedRule}
                        {m.matchMode ? ` (${m.matchMode})` : ""}
                      </button>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusInfo.className}`}
                    >
                      {statusInfo.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
