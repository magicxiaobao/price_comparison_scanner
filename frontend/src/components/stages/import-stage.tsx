import { useCallback, useEffect, useRef, useState } from "react";
import type { FileUploadResponse, RawTable, SupplierFile } from "../../types/file";
import type { TaskInfo } from "../../types/task";
import { getTaskStatus, listFiles, listTables } from "../../lib/api";
import { FileUploader } from "./file-uploader";
import { SupplierConfirmDialog } from "./supplier-confirm-dialog";
import { TableSelector } from "./table-selector";

interface ImportStageProps {
  projectId: string;
}

/** 单个文件的上传+解析追踪信息 */
interface FileTracker {
  fileId: string;
  taskId: string;
  supplierNameGuess: string;
  originalFilename: string;
  status: "parsing" | "completed" | "failed";
  progress: number;
  error: string | null;
}

/** 供应商确认对话框状态 */
interface ConfirmDialogState {
  open: boolean;
  fileId: string;
  suggestedName: string;
  originalFilename: string;
}

export function ImportStage({ projectId }: ImportStageProps) {
  const [files, setFiles] = useState<SupplierFile[]>([]);
  const [tables, setTables] = useState<RawTable[]>([]);
  const [trackers, setTrackers] = useState<Map<string, FileTracker>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    fileId: "",
    suggestedName: "",
    originalFilename: "",
  });
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // 加载已有文件列表和表格列表
  useEffect(() => {
    listFiles(projectId).then(setFiles).catch(() => {});
    listTables(projectId).then(setTables).catch(() => {});
  }, [projectId]);

  // 清理轮询定时器
  useEffect(() => {
    const timers = pollTimers.current;
    return () => {
      for (const timer of timers.values()) {
        clearInterval(timer);
      }
      timers.clear();
    };
  }, []);

  const refreshFiles = useCallback(async () => {
    try {
      const updated = await listFiles(projectId);
      setFiles(updated);
    } catch {
      // 静默处理
    }
  }, [projectId]);

  const refreshTables = useCallback(async () => {
    try {
      const updated = await listTables(projectId);
      setTables(updated);
    } catch {
      // 静默处理
    }
  }, [projectId]);

  const startPolling = useCallback(
    (tracker: FileTracker) => {
      const timer = setInterval(async () => {
        try {
          const info: TaskInfo = await getTaskStatus(tracker.taskId);
          setTrackers((prev) => {
            const next = new Map(prev);
            const current = next.get(tracker.fileId);
            if (!current) return prev;

            if (info.status === "completed") {
              next.set(tracker.fileId, { ...current, status: "completed", progress: 1 });
              clearInterval(pollTimers.current.get(tracker.fileId)!);
              pollTimers.current.delete(tracker.fileId);
              refreshFiles();
              refreshTables();
            } else if (info.status === "failed" || info.status === "cancelled") {
              next.set(tracker.fileId, {
                ...current,
                status: "failed",
                progress: info.progress,
                error: info.error ?? "解析失败",
              });
              clearInterval(pollTimers.current.get(tracker.fileId)!);
              pollTimers.current.delete(tracker.fileId);
            } else {
              next.set(tracker.fileId, { ...current, progress: info.progress });
            }
            return next;
          });
        } catch {
          // 轮询失败时静默处理，下次重试
        }
      }, 1000);
      pollTimers.current.set(tracker.fileId, timer);
    },
    [refreshFiles, refreshTables],
  );

  const handleUploadComplete = useCallback(
    (resp: FileUploadResponse, filename: string) => {
      const tracker: FileTracker = {
        fileId: resp.file_id,
        taskId: resp.task_id,
        supplierNameGuess: resp.supplier_name_guess,
        originalFilename: filename,
        status: "parsing",
        progress: 0,
        error: null,
      };
      setTrackers((prev) => {
        const next = new Map(prev);
        next.set(resp.file_id, tracker);
        return next;
      });
      startPolling(tracker);
    },
    [startPolling],
  );

  const handleError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  }, []);

  const openConfirmDialog = useCallback(
    (fileId: string, suggestedName: string, originalFilename: string) => {
      setConfirmDialog({ open: true, fileId, suggestedName, originalFilename });
    },
    [],
  );

  const handleSupplierConfirmed = useCallback(
    (_supplierName: string) => {
      setConfirmDialog({ open: false, fileId: "", suggestedName: "", originalFilename: "" });
      refreshFiles();
      refreshTables();
    },
    [refreshFiles, refreshTables],
  );

  const handleTableSelectionChange = useCallback(
    (tableId: string, selected: boolean) => {
      setTables((prev) =>
        prev.map((t) => (t.id === tableId ? { ...t, selected } : t)),
      );
    },
    [],
  );

  // 合并已有文件和正在解析的追踪器
  const allFileIds = new Set([
    ...files.map((f) => f.id),
    ...trackers.keys(),
  ]);

  // 汇总信息
  const confirmedCount = files.filter((f) => f.supplier_confirmed).length;
  const allConfirmed = files.length > 0 && confirmedCount === files.length;
  const selectedTableCount = tables.filter((t) => t.selected).length;
  const uniqueSuppliers = new Set(
    files.filter((f) => f.supplier_confirmed).map((f) => f.supplier_name),
  );

  return (
    <div className="space-y-6">
      <FileUploader
        projectId={projectId}
        onUploadComplete={handleUploadComplete}
        onError={handleError}
      />

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {allFileIds.size > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">已上传文件</h3>
          {Array.from(allFileIds).map((fileId) => {
            const file = files.find((f) => f.id === fileId);
            const tracker = trackers.get(fileId);
            return (
              <FileRow
                key={fileId}
                file={file}
                tracker={tracker}
                onConfirmSupplier={openConfirmDialog}
              />
            );
          })}
        </div>
      )}

      {/* 表格选择区域 */}
      {tables.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">解析表格</h3>
          <TableSelector
            projectId={projectId}
            tables={tables}
            onSelectionChange={handleTableSelectionChange}
          />
        </div>
      )}

      {/* 汇总信息 */}
      {allConfirmed && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">
          确认完成，可进入下一步 — {uniqueSuppliers.size} 个供应商，{selectedTableCount} 个表格参与比价
        </div>
      )}

      {/* 供应商确认对话框 */}
      <SupplierConfirmDialog
        open={confirmDialog.open}
        fileId={confirmDialog.fileId}
        projectId={projectId}
        suggestedName={confirmDialog.suggestedName}
        originalFilename={confirmDialog.originalFilename}
        onConfirm={handleSupplierConfirmed}
        onClose={() =>
          setConfirmDialog({ open: false, fileId: "", suggestedName: "", originalFilename: "" })
        }
      />
    </div>
  );
}

function FileRow({
  file,
  tracker,
  onConfirmSupplier,
}: {
  file?: SupplierFile;
  tracker?: FileTracker;
  onConfirmSupplier: (fileId: string, suggestedName: string, originalFilename: string) => void;
}) {
  const filename = file?.original_filename ?? tracker?.originalFilename ?? "未知文件";
  const supplierName = file?.supplier_name ?? tracker?.supplierNameGuess ?? "";
  const isConfirmed = file?.supplier_confirmed ?? false;
  const fileId = file?.id ?? tracker?.fileId ?? "";

  // 确定解析状态
  let parseStatus: "parsing" | "completed" | "failed" = "completed";
  if (tracker) {
    parseStatus = tracker.status;
  }

  const canConfirm = !isConfirmed && parseStatus === "completed" && file;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-gray-900">{filename}</p>
          <p className="text-xs text-gray-500">
            供应商: {supplierName}
            {isConfirmed && (
              <span className="ml-2 text-green-600">已确认</span>
            )}
            {canConfirm && (
              <span className="ml-2 text-amber-600">待确认</span>
            )}
          </p>
        </div>
        <div className="ml-4 flex items-center gap-2">
          {parseStatus === "parsing" && (
            <span className="text-xs text-blue-600">解析中...</span>
          )}
          {parseStatus === "completed" && (
            <span className="text-xs text-green-600">解析完成</span>
          )}
          {parseStatus === "failed" && (
            <span className="text-xs text-red-600">解析失败</span>
          )}
          {canConfirm && (
            <button
              type="button"
              onClick={() => onConfirmSupplier(fileId, supplierName, filename)}
              className="rounded bg-amber-500 px-2 py-1 text-xs text-white hover:bg-amber-600"
            >
              确认供应商
            </button>
          )}
        </div>
      </div>

      {/* 进度条 */}
      {tracker && tracker.status === "parsing" && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-blue-500 transition-all"
            style={{ width: `${Math.round(tracker.progress * 100)}%` }}
          />
        </div>
      )}

      {/* 错误信息 */}
      {tracker?.error && (
        <p className="mt-2 text-xs text-red-600">{tracker.error}</p>
      )}
    </div>
  );
}
