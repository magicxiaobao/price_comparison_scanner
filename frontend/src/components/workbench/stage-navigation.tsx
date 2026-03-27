import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
import type { StageStatuses } from "../../types/project";

interface StageNavigationProps {
  currentStage: number;
  onStageChange: (stage: number) => void;
  stageStatuses?: StageStatuses;
}

const STAGES = [
  { key: "import_status", label: "导入文件", icon: "📁", index: 0 },
  { key: "normalize_status", label: "标准化", icon: "📐", index: 1 },
  { key: "grouping_status", label: "商品归组", icon: "🔗", index: 2 },
  { key: "compliance_status", label: "符合性审查", icon: "✅", index: 3 },
  { key: "comparison_status", label: "比价导出", icon: "📊", index: 4 },
];

export function StageNavigation({
  currentStage,
  onStageChange,
  stageStatuses,
}: StageNavigationProps) {
  const getStatus = (key: string) => {
    if (!stageStatuses) return "pending";
    return stageStatuses[key as keyof StageStatuses] || "pending";
  };

  const getStatusClasses = (status: string, isActive: boolean) => {
    let base = "flex items-center gap-2 px-6 py-2.5 text-sm font-medium transition-colors cursor-pointer data-[state=active]:shadow-none data-[state=active]:bg-transparent data-[state=active]:border-b-2 rounded-none ";
    
    if (isActive) {
      if (status === "dirty") base += "border-orange-500 text-orange-700 ";
      else base += "border-blue-600 text-blue-700 ";
      return base;
    }

    base += "border-transparent ";

    switch (status) {
      case "completed":
        base += "text-green-700 hover:bg-slate-100 hover:text-green-800 ";
        break;
      case "dirty":
        base += "text-orange-600 hover:bg-slate-100 ";
        break;
      case "skipped":
        base += "text-slate-400 border-dashed border-b-slate-300 hover:bg-slate-50 ";
        break;
      default:
        base += "text-slate-500 hover:bg-slate-100 hover:text-slate-700 ";
    }

    return base;
  };

  return (
    <Tabs 
      value={currentStage.toString()} 
      onValueChange={(val) => onStageChange(parseInt(val))}
      className="w-full"
    >
      <TabsList className="flex h-auto w-full justify-start rounded-none border-b border-transparent bg-transparent p-0">
        {STAGES.map((stage) => {
          const isActive = currentStage === stage.index;
          const status = getStatus(stage.key);

          return (
            <TabsTrigger
              key={stage.key}
              value={stage.index.toString()}
              className={getStatusClasses(status, isActive)}
            >
              <span>{stage.icon}</span>
              <span>{stage.label}</span>
              {status === "completed" && <span className="ml-1 text-green-600">✓</span>}
              {status === "dirty" && <span className="ml-1 text-orange-500">⚠</span>}
              {status === "skipped" && <span className="ml-1 text-slate-400">⤑</span>}
            </TabsTrigger>
          );
        })}
      </TabsList>
    </Tabs>
  );
}
