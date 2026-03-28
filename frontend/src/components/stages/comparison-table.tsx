import { useState, useMemo, Fragment } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import type { ComparisonResult, SupplierPrice } from "../../types/comparison";
import { Badge } from "../ui/badge";
import { AnomalyHighlight } from "./anomaly-highlight";

interface ComparisonTableProps {
  results: ComparisonResult[];
}

function getSupplierCellClass(
  unitPrice: number | null,
  row: ComparisonResult,
): string {
  if (unitPrice === null) return "bg-gray-100 bg-stripes";
  const isMinPrice = unitPrice === row.minPrice;
  const isEffectiveMin = unitPrice === row.effectiveMinPrice;
  const effectiveDiffersFromMin =
    row.effectiveMinPrice !== null && row.effectiveMinPrice !== row.minPrice;

  if (isEffectiveMin && effectiveDiffersFromMin) {
    return "ring-2 ring-blue-500 bg-blue-50";
  }
  if (isMinPrice) {
    return "bg-green-100";
  }
  return "";
}

function getRowClass(row: ComparisonResult): string {
  if (row.comparisonStatus === "blocked") return "border-l-4 border-l-red-500";
  if (row.comparisonStatus === "partial")
    return "border-l-4 border-l-yellow-500";
  return "";
}

function statusBadge(status: ComparisonResult["comparisonStatus"]) {
  switch (status) {
    case "comparable":
      return (
        <Badge className="bg-green-100 text-green-800 border-green-200">
          可比
        </Badge>
      );
    case "blocked":
      return (
        <Badge className="bg-red-100 text-red-800 border-red-200">阻断</Badge>
      );
    case "partial":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">
          部分
        </Badge>
      );
  }
}

function formatPrice(v: number | null): string {
  if (v === null) return "-";
  return `¥${v.toFixed(2)}`;
}

export function ComparisonTable({ results }: ComparisonTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Collect unique suppliers in order from the first result's supplierPrices
  const supplierColumns = useMemo(() => {
    if (results.length === 0) return [];
    // Build ordered list of unique supplier file IDs across all results
    const seen = new Set<string>();
    const suppliers: { id: string; name: string }[] = [];
    for (const r of results) {
      for (const sp of r.supplierPrices) {
        if (!seen.has(sp.supplierFileId)) {
          seen.add(sp.supplierFileId);
          suppliers.push({ id: sp.supplierFileId, name: sp.supplierName });
        }
      }
    }
    return suppliers;
  }, [results]);

  const columns = useMemo<ColumnDef<ComparisonResult>[]>(() => {
    const fixedLeft: ColumnDef<ComparisonResult>[] = [
      {
        id: "groupName",
        header: "商品组",
        size: 200,
        minSize: 200,
        cell: ({ row }) => (
          <div className="font-medium text-slate-900 truncate max-w-[200px]">
            {row.original.groupName}
          </div>
        ),
      },
      {
        id: "status",
        header: "状态",
        size: 120,
        minSize: 120,
        cell: ({ row }) => statusBadge(row.original.comparisonStatus),
      },
    ];

    const dynamic: ColumnDef<ComparisonResult>[] = supplierColumns.map(
      (supplier) => ({
        id: `supplier_${supplier.id}`,
        header: supplier.name,
        size: 140,
        minSize: 140,
        cell: ({ row }) => {
          const sp = row.original.supplierPrices.find(
            (p: SupplierPrice) => p.supplierFileId === supplier.id,
          );
          const unitPrice = sp?.unitPrice ?? null;
          const cellClass = getSupplierCellClass(unitPrice, row.original);
          return (
            <div className={`px-2 py-1 rounded ${cellClass}`}>
              {formatPrice(unitPrice)}
            </div>
          );
        },
      }),
    );

    const summary: ColumnDef<ComparisonResult>[] = [
      {
        id: "minPrice",
        header: "最低价",
        size: 110,
        minSize: 110,
        cell: ({ row }) => (
          <span className="text-green-700 font-medium">
            {formatPrice(row.original.minPrice)}
          </span>
        ),
      },
      {
        id: "effectiveMinPrice",
        header: "有效最低",
        size: 110,
        minSize: 110,
        cell: ({ row }) => {
          const differs =
            row.original.effectiveMinPrice !== null &&
            row.original.effectiveMinPrice !== row.original.minPrice;
          return (
            <span
              className={differs ? "text-blue-700 font-medium" : "text-slate-600"}
            >
              {formatPrice(row.original.effectiveMinPrice)}
            </span>
          );
        },
      },
      {
        id: "maxPrice",
        header: "最高价",
        size: 110,
        minSize: 110,
        cell: ({ row }) => (
          <span className="text-slate-600">
            {formatPrice(row.original.maxPrice)}
          </span>
        ),
      },
      {
        id: "avgPrice",
        header: "平均价",
        size: 110,
        minSize: 110,
        cell: ({ row }) => (
          <span className="text-slate-600">
            {formatPrice(row.original.avgPrice)}
          </span>
        ),
      },
      {
        id: "priceDiff",
        header: "差额",
        size: 110,
        minSize: 110,
        cell: ({ row }) => (
          <span className="text-slate-600">
            {formatPrice(row.original.priceDiff)}
          </span>
        ),
      },
      {
        id: "anomaly",
        header: "异常",
        size: 80,
        minSize: 80,
        cell: ({ row }) =>
          row.original.hasAnomaly ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 text-red-500"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
          ) : (
            <span className="text-slate-300">-</span>
          ),
      },
    ];

    return [...fixedLeft, ...dynamic, ...summary];
  }, [supplierColumns]);

  const table = useReactTable({
    data: results,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  // Calculate sticky left offsets for first 2 columns
  const stickyLeftOffsets = [0, 200]; // groupName=0, status=200px

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-lg">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 sticky top-0 z-10">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header, colIdx) => (
                <th
                  key={header.id}
                  className={`px-3 py-2.5 text-left font-semibold text-slate-700 whitespace-nowrap border-b border-slate-200 ${
                    colIdx < 2
                      ? "sticky z-20 bg-slate-50"
                      : ""
                  }`}
                  style={{
                    minWidth: header.getSize(),
                    ...(colIdx < 2
                      ? { left: stickyLeftOffsets[colIdx] }
                      : {}),
                  }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isExpanded = expandedRows.has(row.original.id);
            const hasAnomaly = row.original.hasAnomaly;
            return (
              <Fragment key={row.id}>
                <tr
                  className={`border-b border-slate-100 hover:bg-slate-50/50 ${getRowClass(row.original)} ${
                    hasAnomaly ? "cursor-pointer" : ""
                  }`}
                  onClick={() => hasAnomaly && toggleRow(row.original.id)}
                >
                  {row.getVisibleCells().map((cell, colIdx) => (
                    <td
                      key={cell.id}
                      className={`px-3 py-2 whitespace-nowrap ${
                        colIdx < 2
                          ? "sticky z-10 bg-white"
                          : ""
                      }`}
                      style={
                        colIdx < 2
                          ? { left: stickyLeftOffsets[colIdx] }
                          : undefined
                      }
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
                {isExpanded && hasAnomaly && (
                  <tr>
                    <td colSpan={columns.length}>
                      <AnomalyHighlight
                        anomalies={row.original.anomalyDetails}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

