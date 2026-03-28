import { useEffect } from "react";
import { useProjectStore } from "../../stores/project-store";
import { useComparisonStore } from "../../stores/comparison-store";
import { ComparisonTable } from "./comparison-table";
import { ExportButton } from "./export-button";
import { Button } from "../ui/button";

interface ComparisonStageProps {
  projectId: string;
}

export function ComparisonStage({ projectId }: ComparisonStageProps) {
  const currentProject = useProjectStore((s) => s.currentProject);
  const {
    results,
    isGenerating,
    isLoading,
    error,
    generateComparison,
    loadResults,
  } = useComparisonStore();

  const groupingCompleted =
    currentProject?.stage_statuses?.grouping_status === "completed";

  useEffect(() => {
    if (groupingCompleted) {
      loadResults(projectId);
    }
  }, [projectId, groupingCompleted, loadResults]);

  if (!groupingCompleted) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg shadow-sm">
        <div className="text-center max-w-sm">
          <div className="mx-auto w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">
            请先完成商品归组
          </h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            需要确认所有候选归组后，才能进行比价分析。请返回归组阶段完成操作。
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
      </div>
    );
  }

  if (results.length === 0 && !isGenerating) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg shadow-sm">
        <div className="text-center max-w-sm">
          <div className="mx-auto w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-blue-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">
            尚未生成比价结果
          </h2>
          <p className="text-sm text-slate-500 mb-6 leading-relaxed">
            {error ? (
              <span className="text-red-500">{error}</span>
            ) : (
              '点击下方按钮，系统将对已确认归组的商品组进行价格比较分析。'
            )}
          </p>
          <Button
            onClick={() => generateComparison(projectId)}
            disabled={isGenerating}
            size="lg"
            className="w-full sm:w-auto font-medium shadow-sm bg-blue-600 hover:bg-blue-700"
          >
            {isGenerating ? "生成中..." : "生成比价"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
      {/* 顶部操作栏 */}
      <div className="flex-none p-4 border-b border-slate-200 bg-white flex justify-between items-center">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-slate-900 text-sm">比价结果</h3>
          <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
            {results.length} 组
          </span>
          {error && (
            <span className="text-xs text-red-500">{error}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => generateComparison(projectId)}
            disabled={isGenerating}
          >
            {isGenerating ? (
              <>
                <div className="h-4 w-4 border-2 border-solid border-slate-600 border-r-transparent animate-spin rounded-full mr-2" />
                生成中...
              </>
            ) : (
              "重新生成"
            )}
          </Button>
          <ExportButton projectId={projectId} disabled={isGenerating} />
        </div>
      </div>

      {/* 比价表格 */}
      <div className="flex-1 overflow-auto p-4">
        <ComparisonTable results={results} />
      </div>
    </div>
  );
}
