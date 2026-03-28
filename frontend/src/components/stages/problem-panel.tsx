import { useEffect, useState, useCallback } from "react";
import { useProjectStore } from "../../stores/project-store";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import {
  Menu,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Upload,
  Table,
  Group,
  ClipboardCheck,
  BarChart3,
  AlertTriangle,
  XCircle,
  CheckCircle2,
} from "lucide-react";
import type { ProblemGroup as ProblemGroupType, ProblemStage } from "../../types/problem";

const STAGE_ICON_MAP: Record<string, { icon: typeof Upload; label: string; order: number }> = {
  import:     { icon: Upload,         label: "导入",   order: 0 },
  normalize:  { icon: Table,          label: "标准化", order: 1 },
  grouping:   { icon: Group,          label: "归组",   order: 2 },
  compliance: { icon: ClipboardCheck, label: "符合性", order: 3 },
  comparison: { icon: BarChart3,      label: "比价",   order: 4 },
};

const STAGE_TO_INDEX: Record<ProblemStage, number> = {
  import: 0,
  normalize: 1,
  grouping: 2,
  compliance: 3,
  comparison: 4,
};

interface ProblemPanelProps {
  projectId: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigateStage: (stageIndex: number) => void;
}

export function ProblemPanel({ projectId, isOpen, onOpenChange, onNavigateStage }: ProblemPanelProps) {
  const { problems, refreshProblems, currentProject } = useProjectStore();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [isRefreshing, setIsRefreshing] = useState(false);

  const doRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await refreshProblems(projectId);
    setIsRefreshing(false);
  }, [projectId, refreshProblems]);

  useEffect(() => {
    doRefresh();
  }, [doRefresh]);

  useEffect(() => {
    if (currentProject?.stage_statuses) {
      doRefresh();
    }
  }, [
    currentProject?.stage_statuses?.import_status,
    currentProject?.stage_statuses?.normalize_status,
    currentProject?.stage_statuses?.grouping_status,
    currentProject?.stage_statuses?.compliance_status,
    currentProject?.stage_statuses?.comparison_status,
    doRefresh,
  ]);

  const totalCount = problems.reduce((sum, g) => sum + g.count, 0);

  const sortedGroups = [...problems].sort((a, b) => {
    const orderA = STAGE_ICON_MAP[a.stage]?.order ?? 99;
    const orderB = STAGE_ICON_MAP[b.stage]?.order ?? 99;
    if (orderA !== orderB) return orderA - orderB;
    return a.type.localeCompare(b.type);
  });

  const toggleGroup = (type: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  if (!isOpen) {
    return (
      <div className="w-12 border-l border-slate-200 bg-slate-50 flex flex-col items-center py-4 shrink-0 transition-all duration-300 h-full">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onOpenChange(true)}
          className="text-slate-500 hover:text-slate-900 relative"
          title="展开问题面板"
        >
          <Menu className="h-5 w-5" />
          {totalCount > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1">
              {totalCount}
            </span>
          )}
        </Button>
        <div
          className="mt-4 flex-1 text-xs font-medium text-slate-400 select-none"
          style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
        >
          问题清单
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 border-l border-slate-200 bg-white flex flex-col shrink-0 transition-all duration-300 h-full shadow-sm z-10">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          问题清单
          <Badge
            variant="secondary"
            className={
              totalCount === 0
                ? "bg-green-100 text-green-700 hover:bg-green-100 border-none"
                : "bg-blue-100 text-blue-700 hover:bg-blue-100 border-none"
            }
          >
            {totalCount}
          </Badge>
        </h2>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={doRefresh}
            disabled={isRefreshing}
            className="h-6 w-6 text-slate-400 hover:text-slate-700"
            title="刷新问题清单"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onOpenChange(false)}
            className="h-6 w-6 text-slate-400 hover:text-slate-700"
            title="折叠面板"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        {totalCount === 0 ? (
          <div className="flex flex-col items-center justify-center text-center mt-20 px-4">
            <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mb-3">
              <CheckCircle2 className="h-8 w-8 text-green-400" />
            </div>
            <p className="text-sm text-green-700 font-medium">所有问题已处理，可导出</p>
            <p className="text-xs text-slate-400 mt-1 max-w-[200px]">
              数据完整性检查通过，可进行导出操作。
            </p>
          </div>
        ) : (
          <div className="py-2">
            {sortedGroups.map((group) => (
              <ProblemGroupSection
                key={group.type}
                group={group}
                isExpanded={expandedGroups.has(group.type)}
                onToggle={() => toggleGroup(group.type)}
                onNavigateStage={onNavigateStage}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

function ProblemGroupSection({
  group,
  isExpanded,
  onToggle,
  onNavigateStage,
}: {
  group: ProblemGroupType;
  isExpanded: boolean;
  onToggle: () => void;
  onNavigateStage: (stageIndex: number) => void;
}) {
  const stageInfo = STAGE_ICON_MAP[group.stage];
  const StageIcon = stageInfo?.icon ?? Table;
  const isError = group.severity === "error";

  return (
    <div className="border-b border-slate-50 last:border-b-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
      >
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-slate-400 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />
        )}
        <StageIcon className={`h-4 w-4 shrink-0 ${isError ? "text-red-500" : "text-amber-500"}`} />
        <span className="text-sm text-slate-700 flex-1 truncate">{group.label}</span>
        <Badge
          variant="secondary"
          className={
            isError
              ? "bg-red-100 text-red-700 hover:bg-red-100 border-none text-xs"
              : "bg-amber-100 text-amber-700 hover:bg-amber-100 border-none text-xs"
          }
        >
          {group.count}
        </Badge>
      </button>

      {isExpanded && (
        <div className="px-4 pb-2">
          {group.items.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigateStage(STAGE_TO_INDEX[item.stage] ?? 0)}
              className="w-full flex items-start gap-2 px-2 py-2 rounded-md hover:bg-slate-50 transition-colors text-left group"
            >
              {item.severity === "error" ? (
                <XCircle className="h-3.5 w-3.5 text-red-500 mt-0.5 shrink-0" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
              )}
              <span className="text-xs text-slate-600 flex-1 leading-relaxed group-hover:text-slate-900">
                {item.description}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
