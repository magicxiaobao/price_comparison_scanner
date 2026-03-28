import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useProjectStore } from "../stores/project-store";
import { ImportStage } from "../components/stages/import-stage";
import { StandardizeStage } from "../components/stages/standardize-stage";
import { GroupingStage } from "../components/stages/grouping-stage";
import { ComplianceStage } from "../components/stages/compliance-stage";
import { ComparisonStage } from "../components/stages/comparison-stage";
import { StageNavigation } from "../components/workbench/stage-navigation";
import { useGroupingStore } from "../stores/grouping-store";
import { StageDirtyBanner } from "../components/workbench/stage-dirty-banner";
import { ProblemPanel } from "../components/stages/problem-panel";
import { EvidenceDrawerShell } from "../components/workbench/evidence-drawer-shell";
import { Button } from "../components/ui/button";

function ProjectWorkbench() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { loadProject, loadFiles, loadTables, files, tables, currentProject } =
    useProjectStore();
  const generateGrouping = useGroupingStore(state => state.generateGrouping);

  const [currentStage, setCurrentStage] = useState<number | null>(null);
  const [isProblemPanelOpen, setIsProblemPanelOpen] = useState(false);
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);

  useEffect(() => {
    if (id) {
      loadProject(id);
      loadFiles(id);
      loadTables(id);
    }
  }, [id, loadProject, loadFiles, loadTables]);

  useEffect(() => {
    if (currentProject?.stage_statuses && currentStage === null) {
      const keys = ["import_status", "normalize_status", "grouping_status", "compliance_status", "comparison_status"] as const;
      const statusMap = currentProject.stage_statuses;
      
      let targetStage: number;
      const firstDirty = keys.findIndex(k => statusMap[k] === "dirty");
      
      if (firstDirty !== -1) {
        targetStage = firstDirty;
      } else {
        const firstPending = keys.findIndex(k => statusMap[k] === "pending");
        if (firstPending !== -1) {
          targetStage = firstPending;
        } else {
          targetStage = 4;
        }
      }
      setCurrentStage(targetStage);
    }
  }, [currentProject?.stage_statuses, currentStage]);

  if (!id || currentStage === null) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
      </div>
    );
  }

  const isImportDirty = currentProject?.stage_statuses?.import_status === "dirty";
  const isNormalizeDirty = currentProject?.stage_statuses?.normalize_status === "dirty";
  const isGroupingDirty = currentProject?.stage_statuses?.grouping_status === "dirty";
  const isComplianceDirty = currentProject?.stage_statuses?.compliance_status === "dirty";
  const isComparisonDirty = currentProject?.stage_statuses?.comparison_status === "dirty";

  return (
    <div className="flex flex-col h-screen min-w-[1280px] bg-slate-50 overflow-hidden font-sans">
      <header className="flex-none h-14 bg-[#1e293b] text-white flex items-center justify-between px-6 shadow-sm z-10 transition-colors">
        <div className="flex items-center gap-4">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate("/")}
            className="text-slate-400 hover:text-white hover:bg-slate-800 transition-colors flex items-center gap-1 text-sm font-medium h-8"
          >
            <span aria-hidden="true">&larr;</span> 返回控制台
          </Button>
          <div className="h-4 w-px bg-slate-700"></div>
          <h1 className="text-sm font-semibold tracking-wide flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            {currentProject?.name || "加载中..."}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" className="h-8 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 border hover:text-white">
            项目设置
          </Button>
        </div>
      </header>

      <div className="flex-none bg-white border-b border-slate-200 px-6 pt-3">
        <StageNavigation
          currentStage={currentStage}
          onStageChange={setCurrentStage}
          stageStatuses={currentProject?.stage_statuses}
        />
      </div>

      <div className="flex flex-1 overflow-hidden relative">
        <main className="flex-1 flex flex-col min-w-0 bg-slate-50 relative">
          <div className="flex-none px-6 pt-6">
            {currentStage === 0 && isImportDirty && (
              <StageDirtyBanner
                stageName="导入凭证"
                onRecalculate={() => {}}
              />
            )}
            {currentStage === 1 && isNormalizeDirty && (
              <StageDirtyBanner
                stageName="数据标准化"
                dirtyReason="由于数据文件变更，标准化结果已自动清空。请检查并重新应用清洗规则。"
                onRecalculate={() => {}}
              />
            )}
            {currentStage === 2 && isGroupingDirty && (
              <StageDirtyBanner
                stageName="商品归组"
                dirtyReason="由于上游数据或规则更新，部分归组关系可能受影响，建议重新生成以保障比价准确。"
                onRecalculate={() => id && generateGrouping(id)}
              />
            )}
            {currentStage === 3 && isComplianceDirty && (
              <StageDirtyBanner
                stageName="符合性审查"
                dirtyReason="由于上游数据变更，符合性匹配结果可能受影响，建议重新执行匹配。"
                onRecalculate={() => {}}
              />
            )}
            {currentStage === 4 && isComparisonDirty && (
              <StageDirtyBanner
                stageName="比价分析"
                dirtyReason="由于上游数据变更，比价结果可能受影响，建议重新生成。"
                onRecalculate={() => {}}
              />
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-6 pb-6 pt-2">
            {currentStage === 0 && (
              <ImportStage files={files || []} tables={tables || []} projectId={id} />
            )}
            {currentStage === 1 && (
              <StandardizeStage files={files || []} projectId={id} />
            )}
            {currentStage === 2 && (
              <GroupingStage projectId={id} />
            )}
            {currentStage === 3 && (
              <ComplianceStage projectId={id} />
            )}
            {currentStage === 4 && (
              <ComparisonStage projectId={id} />
            )}
          </div>
        </main>

        <ProblemPanel
          projectId={id}
          isOpen={isProblemPanelOpen}
          onOpenChange={setIsProblemPanelOpen}
          onNavigateStage={setCurrentStage}
        />
      </div>

      <EvidenceDrawerShell 
        isOpen={isEvidenceDrawerOpen} 
        onClose={() => setIsEvidenceDrawerOpen(false)} 
      />
    </div>
  );
}

export default ProjectWorkbench;
