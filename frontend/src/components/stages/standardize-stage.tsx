import { useCallback, useEffect, useRef, useState } from "react";
import type { SupplierFile } from "../../types/file";
import type {
  StandardizedRow,
  ColumnMappingInfo,
  FieldModifyResponse,
} from "../../types/standardization";
import { useProjectStore } from "../../stores/project-store";
import {
  runStandardization,
  getStandardizedRows,
  getColumnMappingInfo,
  modifyStandardizedRow,
  getTaskStatus,
} from "../../lib/api";
import { ColumnMappingPanel } from "./column-mapping-panel";
import { StandardizedDataTable } from "./standardized-data-table";

interface StandardizeStageProps {
  projectId: string;
  files: SupplierFile[];
}

type StageState = "idle" | "running" | "completed" | "failed";

export function StandardizeStage({ projectId, files }: StandardizeStageProps) {
  const { loadProject } = useProjectStore();

  const [state, setState] = useState<StageState>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const [rows, setRows] = useState<StandardizedRow[]>([]);
  const [mappings, setMappings] = useState<ColumnMappingInfo[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>("");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 已确认供应商列表
  const confirmedFiles = files.filter((f) => f.supplier_confirmed);

  // 供应商名称映射: fileId -> supplierName
  const supplierNames: Record<string, string> = {};
  for (const f of confirmedFiles) {
    supplierNames[f.id] = f.supplier_name;
  }

  // 初始选中第一个供应商
  useEffect(() => {
    if (!selectedSupplierId && confirmedFiles.length > 0) {
      setSelectedSupplierId(confirmedFiles[0].id);
    }
  }, [confirmedFiles, selectedSupplierId]);

  // 加载已有的标准化结果
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [rowsData, mappingsData] = await Promise.all([
          getStandardizedRows(projectId),
          getColumnMappingInfo(projectId),
        ]);
        if (!cancelled) {
          setRows(rowsData);
          setMappings(mappingsData);
          if (rowsData.length > 0) {
            setState("completed");
          }
        }
      } catch {
        // 标准化尚未执行，正常情况
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleRunStandardization = useCallback(
    async (force = false) => {
      setState("running");
      setProgress(0);
      setError(null);

      try {
        const { taskId } = await runStandardization(projectId, force);

        // 轮询任务状态
        pollRef.current = setInterval(async () => {
          try {
            const task = await getTaskStatus(taskId);
            setProgress(task.progress);

            if (task.status === "completed") {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;

              const [rowsData, mappingsData] = await Promise.all([
                getStandardizedRows(projectId),
                getColumnMappingInfo(projectId),
              ]);
              setRows(rowsData);
              setMappings(mappingsData);
              setState("completed");
              // 刷新项目状态（normalize_status 已变更）
              await loadProject(projectId);
            } else if (task.status === "failed") {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;
              setState("failed");
              setError(task.error ?? "标准化执行失败");
            }
          } catch (err) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setState("failed");
            setError(err instanceof Error ? err.message : "轮询失败");
          }
        }, 1000);
      } catch (err) {
        setState("failed");
        setError(err instanceof Error ? err.message : "启动标准化失败");
      }
    },
    [projectId, loadProject],
  );

  const handleCellEdit = useCallback(
    async (
      rowId: string,
      field: string,
      newValue: string | number | null,
    ): Promise<boolean> => {
      try {
        const resp: FieldModifyResponse = await modifyStandardizedRow(
          rowId,
          field,
          newValue,
        );
        if (resp.success) {
          // 更新本地行数据
          setRows((prev) =>
            prev.map((r) =>
              r.id === rowId
                ? { ...r, [field]: newValue, isManuallyModified: true }
                : r,
            ),
          );
          // 刷新项目状态（处理 dirtyStages 失效传播）
          await loadProject(projectId);
          return true;
        }
        return false;
      } catch {
        return false;
      }
    },
    [projectId, loadProject],
  );

  // 按供应商过滤行
  const filteredRows = selectedSupplierId
    ? rows.filter((r) => r.supplierFileId === selectedSupplierId)
    : rows;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">标准化</h2>
        <div className="flex items-center gap-3">
          {confirmedFiles.length > 1 && (
            <select
              className="rounded border border-gray-300 px-3 py-1.5 text-sm"
              value={selectedSupplierId}
              onChange={(e) => setSelectedSupplierId(e.target.value)}
            >
              <option value="">全部供应商</option>
              {confirmedFiles.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.supplier_name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* 列名映射面板 */}
      <ColumnMappingPanel mappings={mappings} />

      {/* 标准化预览表格 */}
      <StandardizedDataTable
        rows={filteredRows}
        supplierNames={supplierNames}
        onCellEdit={handleCellEdit}
      />

      {/* 错误提示 */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* 进度条 */}
      {state === "running" && (
        <div className="space-y-1">
          <div className="text-xs text-gray-500">
            标准化执行中... {(progress * 100).toFixed(0)}%
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-300"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={state === "running" || confirmedFiles.length === 0}
          onClick={() => handleRunStandardization(state === "completed")}
        >
          {state === "running"
            ? "执行中..."
            : state === "completed"
              ? "重新标准化"
              : "执行标准化"}
        </button>
        <button
          type="button"
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={mappings.length === 0}
          title="将当前映射保存为全局规则（待实现）"
        >
          保存映射到全局规则
        </button>
      </div>
    </div>
  );
}
