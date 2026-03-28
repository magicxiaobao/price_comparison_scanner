import { useEffect, useState } from "react";
import { Button } from "../ui/button";
import { useComplianceStore } from "../../stores/compliance-store";
import { RequirementEditor } from "./requirement-editor";
import { RequirementImporter } from "./requirement-importer";
import { ComplianceMatrix } from "./compliance-matrix";
import { EvidenceDetailPanel } from "./evidence-detail-panel";

interface ComplianceStageProps {
  projectId: string;
}

export function ComplianceStage({ projectId }: ComplianceStageProps) {
  const {
    requirements,
    matrix,
    selectedMatchId,
    isEvaluating,
    isLoading,
    error,
    loadRequirements,
    loadMatrix,
    runEvaluation,
    setSelectedMatch,
  } = useComplianceStore();

  const [showEditor, setShowEditor] = useState(false);
  const [showImporter, setShowImporter] = useState(false);

  useEffect(() => {
    loadRequirements(projectId);
    loadMatrix(projectId);
  }, [projectId, loadRequirements, loadMatrix]);

  if (isLoading && requirements.length === 0 && !matrix) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
      </div>
    );
  }

  // Empty state: no requirements yet
  if (requirements.length === 0 && !showEditor) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg shadow-sm">
        <div className="text-center max-w-sm">
          <div className="mx-auto w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">尚未设置需求标准</h2>
          <p className="text-sm text-slate-500 mb-6 leading-relaxed">
            添加项目的需求标准，系统将自动比对各供应商的符合情况。此步骤为可选，也可跳过直接进入比价。
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              onClick={() => setShowEditor(true)}
              size="lg"
              className="font-medium shadow-sm bg-blue-600 hover:bg-blue-700"
            >
              录入需求标准
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="font-medium"
              onClick={() => setShowImporter(true)}
            >
              从 Excel 导入
            </Button>
          </div>
          <p className="text-xs text-slate-400 mt-4">
            可随时跳过此步骤，直接进入比价阶段
          </p>
        </div>
        <RequirementImporter projectId={projectId} open={showImporter} onClose={() => setShowImporter(false)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] gap-4">
      {/* Top action bar */}
      <div className="flex-none flex items-center justify-between px-1">
        <h3 className="text-sm font-semibold text-slate-900">符合性审查</h3>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() => setShowImporter(true)}
          >
            导入模板
          </Button>
          <Button
            size="sm"
            className="h-8 text-xs bg-blue-600 hover:bg-blue-700"
            onClick={() => runEvaluation(projectId)}
            disabled={isEvaluating || requirements.length === 0}
          >
            {isEvaluating ? (
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 border-2 border-white border-r-transparent animate-spin rounded-full" />
                匹配中...
              </span>
            ) : (
              "执行匹配"
            )}
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex-none p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm flex items-center justify-between mx-1">
          <span>{error}</span>
          <button
            onClick={() => useComplianceStore.setState({ error: null })}
            className="text-red-400 hover:text-red-600"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      )}

      {/* Upper area: Requirement editor */}
      <div className="flex-none px-1">
        <RequirementEditor projectId={projectId} />
      </div>

      {/* Lower area: Compliance matrix */}
      {matrix && matrix.rows.length > 0 && (
        <div className="flex-1 min-h-0 px-1">
          <h3 className="text-sm font-semibold text-slate-900 mb-2">符合性矩阵</h3>
          <ComplianceMatrix
            matrix={matrix}
            selectedMatchId={selectedMatchId}
            onSelectMatch={setSelectedMatch}
          />
        </div>
      )}

      {/* Evidence panel (Sheet) */}
      <EvidenceDetailPanel
        projectId={projectId}
        matchId={selectedMatchId}
        onClose={() => setSelectedMatch(null)}
      />

      {/* Import dialog */}
      <RequirementImporter
        projectId={projectId}
        open={showImporter}
        onClose={() => setShowImporter(false)}
      />
    </div>
  );
}
