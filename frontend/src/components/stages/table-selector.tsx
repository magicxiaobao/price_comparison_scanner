import { useState } from "react";
import type { RawTable, RawTableData } from "../../types/file";
import { toggleTableSelection } from "../../lib/api";

interface TableSelectorProps {
  projectId: string;
  tables: RawTable[];
  onSelectionChange: (tableId: string, selected: boolean) => void;
}

function parseRawData(raw: string | RawTableData): RawTableData | null {
  if (typeof raw === "object" && raw !== null) {
    return raw as RawTableData;
  }
  try {
    return JSON.parse(raw) as RawTableData;
  } catch {
    return null;
  }
}

export function TableSelector({ projectId, tables, onSelectionChange }: TableSelectorProps) {
  // 按 supplier_file_id 分组
  const grouped = new Map<string, RawTable[]>();
  for (const t of tables) {
    const key = t.supplier_file_id;
    const list = grouped.get(key) ?? [];
    list.push(t);
    grouped.set(key, list);
  }

  if (tables.length === 0) {
    return <p className="text-sm text-gray-400">暂无解析表格</p>;
  }

  return (
    <div className="space-y-4">
      {Array.from(grouped.entries()).map(([fileId, fileTables]) => {
        const first = fileTables[0];
        const label = first.original_filename ?? first.supplier_name ?? fileId;
        return (
          <div key={fileId} className="rounded-lg border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-4 py-2">
              <p className="text-sm font-medium text-gray-700">{label}</p>
            </div>
            <div className="divide-y divide-gray-100">
              {fileTables.map((table) => (
                <TableRow
                  key={table.id}
                  table={table}
                  projectId={projectId}
                  onSelectionChange={onSelectionChange}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TableRow({
  table,
  projectId,
  onSelectionChange,
}: {
  table: RawTable;
  projectId: string;
  onSelectionChange: (tableId: string, selected: boolean) => void;
}) {
  const [selected, setSelected] = useState(table.selected);
  const [expanded, setExpanded] = useState(false);
  const [toggling, setToggling] = useState(false);

  const tableName = table.sheet_name ?? `表格 ${table.table_index + 1}`;
  const parsed = expanded ? parseRawData(table.raw_data) : null;

  const handleToggle = async () => {
    setToggling(true);
    try {
      const resp = await toggleTableSelection(table.id, projectId);
      setSelected(resp.selected);
      onSelectionChange(table.id, resp.selected);
    } catch {
      // 静默处理
    } finally {
      setToggling(false);
    }
  };

  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          checked={selected}
          disabled={toggling}
          onChange={handleToggle}
          className="h-4 w-4 rounded border-gray-300 text-blue-600"
        />
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex-1 text-left"
        >
          <span className="text-sm text-gray-800">{tableName}</span>
          <span className="ml-3 text-xs text-gray-400">
            {table.row_count} 行 x {table.column_count} 列
          </span>
          <span className="ml-2 text-xs text-gray-400">
            {expanded ? "收起" : "预览"}
          </span>
        </button>
      </div>

      {expanded && parsed && (
        <div className="mt-2 overflow-x-auto rounded border border-gray-100">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="bg-gray-50">
                {parsed.headers.map((h, i) => (
                  <th key={i} className="px-2 py-1 text-left font-medium text-gray-600">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parsed.rows.slice(0, 5).map((row, ri) => (
                <tr key={ri} className="border-t border-gray-50">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-2 py-1 text-gray-700">
                      {cell ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {parsed.rows.length > 5 && (
            <p className="px-2 py-1 text-xs text-gray-400">
              ... 共 {parsed.rows.length} 行，仅显示前 5 行
            </p>
          )}
        </div>
      )}
    </div>
  );
}
