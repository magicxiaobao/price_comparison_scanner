import { useState, useCallback, useEffect, useRef } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import type {
  StandardizedRow,
  StandardFieldKey,
} from "../../types/standardization";
import {
  STANDARD_FIELD_LABELS,
  REQUIRED_FIELDS,
} from "../../types/standardization";

interface StandardizedDataTableProps {
  rows: StandardizedRow[];
  supplierNames: Record<string, string>;
  onCellEdit: (
    rowId: string,
    field: string,
    newValue: string | number | null,
  ) => Promise<boolean>;
}

/** 可编辑单元格组件 */
function EditableCell({
  value,
  rowId,
  field,
  isModified,
  isRequired,
  onSave,
}: {
  value: string | number | null;
  rowId: string;
  field: string;
  isModified: boolean;
  isRequired: boolean;
  onSave: (rowId: string, field: string, newValue: string | number | null) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(String(value ?? ""));
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const handleSave = useCallback(async () => {
    if (!editing) return;
    setSaving(true);
    const trimmed = editValue.trim();
    const newValue = trimmed === "" ? null : trimmed;
    const ok = await onSave(rowId, field, newValue);
    setSaving(false);
    if (ok) {
      setEditing(false);
    }
  }, [editing, editValue, rowId, field, onSave]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSave();
      } else if (e.key === "Escape") {
        setEditValue(String(value ?? ""));
        setEditing(false);
      }
    },
    [handleSave, value],
  );

  const isEmpty = value == null || value === "";
  const showRequiredWarning = isRequired && isEmpty;

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="w-full rounded border border-blue-400 px-1.5 py-0.5 text-xs outline-none focus:ring-1 focus:ring-blue-300"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        disabled={saving}
      />
    );
  }

  return (
    <div
      className={`group relative cursor-text rounded px-1.5 py-0.5 text-xs ${
        showRequiredWarning
          ? "bg-red-50 text-red-400 ring-1 ring-red-200"
          : "hover:bg-blue-50"
      }`}
      onDoubleClick={() => {
        setEditValue(String(value ?? ""));
        setEditing(true);
      }}
    >
      {isEmpty ? (
        <span className="italic text-gray-300">
          {showRequiredWarning ? "必填" : "-"}
        </span>
      ) : (
        <span>{String(value)}</span>
      )}
      {isModified && (
        <span
          className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-orange-400"
          title="已手动修改"
        />
      )}
    </div>
  );
}

/** 标准字段列 key 列表 */
const FIELD_KEYS: StandardFieldKey[] = [
  "product_name",
  "spec_model",
  "unit",
  "quantity",
  "unit_price",
  "total_price",
  "tax_rate",
  "delivery_period",
  "remark",
];

export function StandardizedDataTable({
  rows,
  supplierNames,
  onCellEdit,
}: StandardizedDataTableProps) {
  const columns: ColumnDef<StandardizedRow, unknown>[] = [
    {
      id: "rowIndex",
      header: "#",
      size: 40,
      accessorFn: (row) => row.rowIndex + 1,
      cell: (info) => (
        <span className="text-xs text-gray-400">{info.getValue() as number}</span>
      ),
    },
    {
      id: "supplierName",
      header: "供应商",
      size: 100,
      accessorFn: (row) => supplierNames[row.supplierFileId] ?? "-",
      cell: (info) => (
        <span className="text-xs font-medium">{info.getValue() as string}</span>
      ),
    },
    ...FIELD_KEYS.map(
      (fieldKey): ColumnDef<StandardizedRow, unknown> => ({
        id: fieldKey,
        header: STANDARD_FIELD_LABELS[fieldKey],
        size: fieldKey === "product_name" ? 180 : fieldKey === "remark" ? 140 : 90,
        accessorFn: (row) => row[fieldKey],
        cell: (info) => (
          <EditableCell
            value={info.getValue() as string | number | null}
            rowId={info.row.original.id}
            field={fieldKey}
            isModified={info.row.original.isManuallyModified}
            isRequired={REQUIRED_FIELDS.includes(fieldKey)}
            onSave={onCellEdit}
          />
        ),
      }),
    ),
    {
      id: "confidence",
      header: "置信度",
      size: 70,
      accessorFn: (row) => row.confidence,
      cell: (info) => {
        const val = info.getValue() as number;
        const low = val < 0.8;
        return (
          <span
            className={`inline-block rounded px-1.5 py-0.5 text-xs font-mono ${
              low
                ? "bg-yellow-100 text-yellow-800"
                : "bg-green-50 text-green-700"
            }`}
          >
            {(val * 100).toFixed(0)}%
          </span>
        );
      },
    },
  ];

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
        暂无标准化数据。请先执行标准化。
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="w-full">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-gray-200 bg-gray-50">
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold text-gray-600"
                  style={{ width: header.getSize() }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const needsReview = row.original.needsReview;
            return (
              <tr
                key={row.id}
                className={`border-b border-gray-50 ${
                  needsReview ? "bg-yellow-50" : "hover:bg-gray-50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-1.5">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
