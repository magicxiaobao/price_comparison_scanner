import { useComparisonStore } from "../../stores/comparison-store";
import { Button } from "../ui/button";

interface ExportButtonProps {
  projectId: string;
  disabled?: boolean;
}

export function ExportButton({ projectId, disabled }: ExportButtonProps) {
  const { isExporting, exportProgress, exportError, exportReport } =
    useComparisonStore();

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
    </div>
  );
}
