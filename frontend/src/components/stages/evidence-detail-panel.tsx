import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "../ui/sheet";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Separator } from "../ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { useComplianceStore } from "../../stores/compliance-store";
import { STATUS_STYLES } from "../../types/compliance";
import type { ComplianceMatrixCell } from "../../types/compliance";

interface EvidenceDetailPanelProps {
  projectId: string;
  matchId: string | null;
  onClose: () => void;
}

export function EvidenceDetailPanel({ projectId, matchId, onClose }: EvidenceDetailPanelProps) {
  const { matrix, confirmMatchStatus, acceptMatchResult } = useComplianceStore();

  const findCell = (): {
    cell: ComplianceMatrixCell;
    requirementTitle: string;
    supplierName: string;
  } | null => {
    if (!matrix || !matchId) return null;
    for (const row of matrix.rows) {
      for (const [supplierId, cell] of Object.entries(row.suppliers)) {
        if (cell.matchId === matchId) {
          return {
            cell,
            requirementTitle: row.requirement.title,
            supplierName: matrix.supplierNames[supplierId] || supplierId,
          };
        }
      }
    }
    return null;
  };

  const found = findCell();

  const handleConfirmStatus = async (status: string) => {
    if (!matchId) return;
    await confirmMatchStatus(matchId, projectId, status);
  };

  const handleToggleAcceptable = async () => {
    if (!matchId || !found) return;
    await acceptMatchResult(matchId, projectId, !found.cell.isAcceptable);
  };

  return (
    <Sheet open={!!matchId} onOpenChange={(val) => !val && onClose()}>
      <SheetContent side="right" className="w-[400px] sm:max-w-[400px]">
        <SheetHeader>
          <SheetTitle>匹配证据详情</SheetTitle>
          <SheetDescription>
            查看并确认匹配结果
          </SheetDescription>
        </SheetHeader>

        {found ? (
          <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-5">
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500 mb-1">需求项</p>
                <p className="text-sm font-medium text-slate-800">{found.requirementTitle}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-1">供应商</p>
                <p className="text-sm font-medium text-slate-800">{found.supplierName}</p>
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500 mb-1">匹配状态</p>
                <div className="flex items-center gap-2">
                  {(() => {
                    const style = STATUS_STYLES[found.cell.status];
                    return (
                      <Badge className={`${style.bg} ${style.text} border ${style.border}`}>
                        {style.label}
                      </Badge>
                    );
                  })()}
                  {found.cell.needsReview && (
                    <Badge variant="outline" className="text-orange-600 border-orange-300 bg-orange-50 text-xs">
                      待确认
                    </Badge>
                  )}
                  {found.cell.isAcceptable && (
                    <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50 text-xs">
                      已标记可接受
                    </Badge>
                  )}
                </div>
              </div>

              <div>
                <p className="text-xs text-slate-500 mb-1">证据原文</p>
                {found.cell.evidenceText ? (
                  <div className="bg-slate-50 border border-slate-200 rounded-md p-3 text-sm text-slate-700 leading-relaxed">
                    {found.cell.evidenceText}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">无证据文本</p>
                )}
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500 mb-2">修改匹配状态</p>
                <Select
                  value={found.cell.status}
                  onValueChange={handleConfirmStatus}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="match">符合</SelectItem>
                    <SelectItem value="partial">部分符合</SelectItem>
                    <SelectItem value="no_match">不符合</SelectItem>
                    <SelectItem value="unclear">待定</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {found.cell.status === "partial" && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-700">标记为可接受</p>
                  <Button
                    variant={found.cell.isAcceptable ? "default" : "outline"}
                    size="sm"
                    className="h-7 text-xs"
                    onClick={handleToggleAcceptable}
                  >
                    {found.cell.isAcceptable ? "已标记可接受" : "标记可接受"}
                  </Button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-sm text-slate-400 px-4">
            未找到匹配数据
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
