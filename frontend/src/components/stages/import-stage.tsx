import { useCallback, useEffect, useRef, useState } from "react";
import type { FileUploadResponse, RawTable, SupplierFile } from "../../types/file";
import type { TaskInfo } from "../../types/task";
import { deleteFile, getTaskStatus } from "../../lib/api";
import { useProjectStore } from "../../stores/project-store";
import { FileUploader } from "./file-uploader";
import { SupplierConfirmDialog } from "./supplier-confirm-dialog";
import { TableSelector } from "./table-selector";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";

interface ImportStageProps {
  projectId: string;
  files: SupplierFile[];
  tables: RawTable[];
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

export function ImportStage({ projectId, files, tables }: ImportStageProps) {
  const { loadFiles, loadTables, addUploadTask, updateTaskStatus, removeTask, importProgress } =
    useProjectStore();

  const [trackers, setTrackers] = useState<Map<string, FileTracker>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    fileId: "",
    suggestedName: "",
    originalFilename: "",
  });
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

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

  const refreshData = useCallback(async () => {
    await Promise.all([loadFiles(projectId), loadTables(projectId)]);
  }, [projectId, loadFiles, loadTables]);

  const startPolling = useCallback(
    (tracker: FileTracker) => {
      const timer = setInterval(async () => {
        try {
          const info: TaskInfo = await getTaskStatus(tracker.taskId);
          updateTaskStatus(tracker.taskId, info);

          setTrackers((prev) => {
            const next = new Map(prev);
            const current = next.get(tracker.fileId);
            if (!current) return prev;

            if (info.status === "completed") {
              next.set(tracker.fileId, { ...current, status: "completed", progress: 1 });
              clearInterval(pollTimers.current.get(tracker.fileId)!);
              pollTimers.current.delete(tracker.fileId);
              removeTask(tracker.taskId);
              refreshData();
            } else if (info.status === "failed" || info.status === "cancelled") {
              next.set(tracker.fileId, {
                ...current,
                status: "failed",
                progress: info.progress,
                error: info.error ?? "解析失败",
              });
              clearInterval(pollTimers.current.get(tracker.fileId)!);
              pollTimers.current.delete(tracker.fileId);
              removeTask(tracker.taskId);
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
    [refreshData, updateTaskStatus, removeTask],
  );

  const handleUploadComplete = useCallback(
    (resp: FileUploadResponse, filename: string) => {
      addUploadTask(resp.task_id, resp.file_id);

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
    [startPolling, addUploadTask],
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
      refreshData();
    },
    [refreshData],
  );

  const handleTableSelectionChange = useCallback(
    (tableId: string, selected: boolean) => {
      // 乐观更新 Store 中的 tables（Store 里的 tables 由 loadTables 管理，
      // 这里直接更新 Store 以保持一致性）
      useProjectStore.setState((state) => ({
        tables: state.tables.map((t) =>
          t.id === tableId ? { ...t, selected } : t,
        ),
      }));
    },
    [],
  );

  // 合并已有文件和正在解析的追踪器
  const allFileIds = new Set([
    ...files.map((f) => f.id),
    ...trackers.keys(),
  ]);

  // 汇总信息
  const progress = importProgress();

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
                onDeleteSuccess={refreshData}
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
      {progress.allConfirmed && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">
          确认完成，可进入下一步 — {progress.confirmedFiles} 个供应商，{progress.selectedTables} 个表格参与比价
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
  onDeleteSuccess,
}: {
  file?: SupplierFile;
  tracker?: FileTracker;
  onConfirmSupplier: (fileId: string, suggestedName: string, originalFilename: string) => void;
  onDeleteSuccess: () => void;
}) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
  const canDelete = !isConfirmed && parseStatus !== "parsing";

  const handleDelete = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteFile(fileId);
      setDeleteDialogOpen(false);
      onDeleteSuccess();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "删除失败";
      setDeleteError(detail);
    } finally {
      setDeleting(false);
    }
  };

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
          {canDelete && (
            <button
              type="button"
              onClick={() => setDeleteDialogOpen(true)}
              disabled={deleting}
              className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
              title="删除文件"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </button>
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

      {/* OCR 未安装提示 */}
      {tracker?.error && tracker.error.includes("OCR") && (
        <div className="mt-2 rounded-md bg-blue-50 p-3 text-sm text-blue-800">
          <p className="font-medium">OCR 扩展未安装</p>
          <p className="mt-1 text-xs text-blue-700">
            当前文件为扫描版 PDF，需要 OCR 扩展才能自动识别表格内容。
          </p>
          <p className="mt-1 text-xs text-blue-600">
            建议：请将文件内容手动复制到 Excel 后重新导入。
          </p>
        </div>
      )}

      {/* 其他错误信息 */}
      {tracker?.error && !tracker.error.includes("OCR") && (
        <p className="mt-2 text-xs text-red-600">{tracker.error}</p>
      )}

      {/* 删除错误提示 */}
      {deleteError && (
        <p className="mt-2 text-xs text-red-600">{deleteError}</p>
      )}

      {/* 删除确认对话框 */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除文件「{filename}」吗？删除后无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
              disabled={deleting}
              onClick={handleDelete}
            >
              {deleting ? "删除中..." : "删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
