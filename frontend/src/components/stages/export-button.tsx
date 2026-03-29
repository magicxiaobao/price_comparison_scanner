import { useComparisonStore } from "../../stores/comparison-store";
import { Button } from "../ui/button";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";

interface ExportButtonProps {
  projectId: string;
  disabled?: boolean;
}

export function ExportButton({ projectId, disabled }: ExportButtonProps) {
  const {
    isExporting,
    exportProgress,
    exportError,
    exportFilePath,
    exportFileName,
    exportReport,
    clearExportResult,
  } = useComparisonStore();

  const handleOpenFile = async () => {
    if (exportFilePath) {
      try {
        await openPath(exportFilePath);
      } catch {
        await revealItemInDir(exportFilePath).catch(() => {});
      }
    }
  };

  const handleRevealInDir = async () => {
    if (exportFilePath) {
      await revealItemInDir(exportFilePath).catch(() => {});
    }
  };

  return (
    <div className="flex items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        onClick={() => exportReport(projectId)}
        disabled={disabled || isExporting}
        className="gap-2"
      >
        {isExporting ? (
          <>
            <div className="h-4 w-4 border-2 border-solid border-slate-600 border-r-transparent animate-spin rounded-full" />
            导出中 {Math.round(exportProgress * 100)}%
          </>
        ) : (
          <>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            导出底稿
          </>
        )}
      </Button>
      {exportError && (
        <span className="text-xs text-red-500">{exportError}</span>
      )}
      {exportFilePath && (
        <span className="flex items-center gap-1 text-xs text-green-600">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5 flex-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <button
            type="button"
            className="hover:underline hover:text-green-700 cursor-pointer truncate max-w-[200px]"
            onClick={handleOpenFile}
            title="点击打开文件"
          >
            {exportFileName ?? "导出完成"}
          </button>
          <button
            type="button"
            className="text-slate-400 hover:text-blue-600 flex-none"
            onClick={handleRevealInDir}
            title="在 Finder 中显示"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
            </svg>
          </button>
          <button
            type="button"
            className="text-slate-400 hover:text-slate-600 flex-none"
            onClick={clearExportResult}
            aria-label="关闭"
          >
            ×
          </button>
        </span>
      )}
    </div>
  );
}
