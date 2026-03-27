import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "../ui/dialog";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import type { CommodityGroup } from "../../types/grouping";

interface GroupSplitDialogProps {
  group: CommodityGroup | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (newGroups: string[][]) => Promise<void>;
}

export function GroupSplitDialog({ group, open, onClose, onConfirm }: GroupSplitDialogProps) {
  const [allocations, setAllocations] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [binCount, setBinCount] = useState(2);

  useEffect(() => {
    if (group && open) {
      const initial: Record<string, number> = {};
      const half = Math.ceil(group.members.length / 2);
      group.members.forEach((m, idx) => {
        initial[m.standardizedRowId] = idx < half ? 0 : 1;
      });
      setAllocations(initial);
      setBinCount(2);
      setIsSubmitting(false);
    }
  }, [group, open]);

  if (!group) return null;

  const handleMove = (rowId: string, targetBinIndex: number) => {
    setAllocations(prev => ({
      ...prev,
      [rowId]: targetBinIndex
    }));
  };

  const handleRemoveBin = (indexToRemove: number) => {
    setBinCount(prev => prev - 1);
    setAllocations(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(k => {
        if (next[k] > indexToRemove) {
          next[k] = next[k] - 1;
        }
      });
      return next;
    });
  };

  const nonEmptyBins = Array.from({ length: binCount }).filter((_, i) => Object.values(allocations).filter(v => v === i).length > 0);
  const isValid = nonEmptyBins.length >= 2;

  const handleConfirm = async () => {
    if (!isValid) return;
    setIsSubmitting(true);
    try {
      const newGroups: string[][] = [];
      Array.from({ length: binCount }).forEach((_, i) => {
        const items = Object.entries(allocations).filter(([, bin]) => bin === i).map(([id]) => id);
        if (items.length > 0) newGroups.push(items);
      });
      await onConfirm(newGroups);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(val) => !val && !isSubmitting && onClose()}>
      <DialogContent className="sm:max-w-[1000px]">
        <DialogHeader>
          <DialogTitle>拆分候选归组</DialogTitle>
          <DialogDescription>
            将选定的商品明细拆分为多个新组。可通过“添加组”分发多目标。每组需至少分配 1 项明细。
          </DialogDescription>
        </DialogHeader>
        
        <div className="flex gap-4 mt-4 h-[440px] overflow-x-auto pb-2">
          {Array.from({ length: binCount }).map((_, binIndex) => {
            const binItems = group.members.filter(m => allocations[m.standardizedRowId] === binIndex);
            return (
              <div key={binIndex} className="min-w-[240px] max-w-[300px] flex-1 flex flex-col border border-slate-200 rounded-md overflow-hidden bg-slate-50">
                <div className="bg-slate-100 p-2 border-b border-slate-200 font-semibold text-sm flex items-center gap-2">
                  <span className="flex-1">目标组 {String.fromCharCode(65 + binIndex)}</span>
                  <span className="text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full text-xs">{binItems.length} 项</span>
                  {binIndex >= 2 && binItems.length === 0 && (
                    <Button variant="ghost" size="sm" className="h-5 w-5 p-0 text-slate-400 hover:text-red-500" onClick={() => handleRemoveBin(binIndex)} aria-label="删除组">
                      ×
                    </Button>
                  )}
                </div>
                <ScrollArea className="flex-1 p-2">
                  <div className="space-y-2">
                    {binItems.map(member => (
                      <div key={member.standardizedRowId} className="p-2.5 border border-slate-200 rounded bg-white text-xs flex flex-col gap-2 shadow-sm transition-colors hover:border-blue-300">
                        <div>
                          <div className="font-medium truncate text-slate-800" title={member.supplierName}>{member.supplierName}</div>
                          <div className="text-slate-500 truncate mt-0.5" title={member.productName}>
                            {member.productName} {member.specModel && `(${member.specModel})`}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {Array.from({ length: binCount }).map((_, targetBinIndex) => {
                            if (targetBinIndex === binIndex) return null;
                            return (
                              <Button 
                                key={targetBinIndex} 
                                variant="secondary" 
                                size="sm" 
                                className="h-6 px-2 text-[10px] bg-slate-100 hover:bg-blue-100 hover:text-blue-700" 
                                onClick={() => handleMove(member.standardizedRowId, targetBinIndex)}
                              >
                                移至 {String.fromCharCode(65 + targetBinIndex)}
                              </Button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            );
          })}

          {binCount < 5 && (
            <div className="min-w-[120px] flex-shrink-0 flex flex-col items-center justify-center p-4">
              <Button variant="outline" onClick={() => setBinCount(b => b + 1)} className="border-dashed border-2 text-slate-500 hover:bg-slate-50 px-6 py-8 h-auto">
                <div className="flex flex-col items-center gap-2">
                  <span className="text-xl">+</span>
                  <span>添加组</span>
                </div>
              </Button>
            </div>
          )}
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>取消</Button>
          <Button onClick={handleConfirm} disabled={!isValid || isSubmitting}>
            {isSubmitting ? "正在拆分..." : "确定拆分"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
