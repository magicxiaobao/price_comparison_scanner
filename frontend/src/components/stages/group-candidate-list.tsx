import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import type { CommodityGroup } from "../../types/grouping";
import { cn } from "../../lib/utils";

interface GroupCandidateListProps {
  groups: CommodityGroup[];
  activeGroupId: string | null;
  onSelectGroup: (groupId: string) => void;
  onConfirm?: (groupId: string) => void;
}

export function GroupCandidateList({ groups, activeGroupId, onSelectGroup, onConfirm }: GroupCandidateListProps) {
  const highGroups = groups.filter(g => g.confidenceLevel === "high");
  const mediumGroups = groups.filter(g => g.confidenceLevel === "medium");
  const lowGroups = groups.filter(g => g.confidenceLevel === "low");

  const renderGroupList = (list: CommodityGroup[], title: string, colorClass: string) => {
    if (list.length === 0) return null;
    return (
      <div className="mb-6">
        <h3 className={cn("text-xs font-semibold uppercase tracking-wider mb-3 px-1", colorClass)}>
          {title} ({list.length})
        </h3>
        <div className="space-y-3">
          {list.map(group => (
            <Card 
              key={group.id} 
              className={cn(
                "p-4 cursor-pointer hover:border-blue-400 transition-colors",
                activeGroupId === group.id ? "border-blue-500 bg-blue-50/50 shadow-sm" : "border-slate-200 bg-white"
              )}
              onClick={() => onSelectGroup(group.id)}
            >
              <div className="flex justify-between items-start mb-2">
                <div className="font-medium text-slate-900 line-clamp-1" title={group.groupName}>
                  {group.groupName || "未命名归组"}
                </div>
                <Badge variant="outline" className={cn(
                  "shrink-0 ml-2 whitespace-nowrap",
                  group.status === "candidate" ? "bg-blue-50 text-blue-700 border-blue-200" :
                  group.status === "confirmed" ? "bg-green-50 text-green-700 border-green-200" :
                  "bg-slate-100 text-slate-700 border-slate-200"
                )}>
                  {group.status === "candidate" ? "待确认" : group.status === "confirmed" ? "已确认" : group.status}
                </Badge>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                <span className="flex items-center gap-1 font-medium">
                  <svg className="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                  {group.memberCount} 项
                </span>
                <span className="text-slate-300">|</span>
                <span>匹配度: {(group.matchScore * 100).toFixed(0)}%</span>
              </div>
              <p className="text-xs text-slate-400 line-clamp-1 mb-3" title={group.matchReason}>
                {group.matchReason}
              </p>
              {group.status === "candidate" && (
                <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                  <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-100" onClick={(e) => { e.stopPropagation(); onConfirm?.(group.id); }}>
                    一键确认
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="pb-16">
      {renderGroupList(highGroups, "高置信度 (推荐一键确认)", "text-emerald-600")}
      {renderGroupList(mediumGroups, "中置信度 (需人工复核)", "text-amber-600")}
      {renderGroupList(lowGroups, "低置信度 / 奇异项", "text-slate-500")}
    </div>
  );
}
