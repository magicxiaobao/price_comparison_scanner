import { useEffect, useState } from "react";
import { DndContext, DragOverlay, DragStartEvent, DragEndEvent, pointerWithin } from '@dnd-kit/core';
import { useProjectStore } from "../../stores/project-store";
import { moveMember, confirmGroup, splitGroup, mergeGroups, markNotComparable } from "../../lib/api";
import { GroupSplitDialog } from "./group-split-dialog";
import { DraggableMemberRow } from "./group-drag-zone";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../ui/dialog";
import type { CommodityGroup, GroupMemberSummary } from "../../types/grouping";
import { useGroupingStore } from "../../stores/grouping-store";
import { GroupCandidateList } from "./group-candidate-list";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { ScrollArea } from "../ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";

interface GroupingStageProps {
  projectId: string;
}

export function GroupingStage({ projectId }: GroupingStageProps) {
  const { groups, loadGroups, generateGrouping, isGenerating, isLoading, error, selectedGroupId, selectGroup } = useGroupingStore();
  const [activeDragItem, setActiveDragItem] = useState<{ member: GroupMemberSummary, sourceGroupId: string } | null>(null);
  const [isMoving, setIsMoving] = useState(false);
  const [dragError, setDragError] = useState<string | null>(null);
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);
  const [splitDialogGroup, setSplitDialogGroup] = useState<CommodityGroup | null>(null);
  const [mergeConfirmOpen, setMergeConfirmOpen] = useState(false);
  const [notComparableConfirmGroup, setNotComparableConfirmGroup] = useState<string | null>(null);

  const handleToggleGroupSelect = (groupId: string) => {
    setSelectedGroupIds(prev =>
      prev.includes(groupId) ? prev.filter(id => id !== groupId) : [...prev, groupId]
    );
  };

  const handleAction = async (actionFn: () => Promise<unknown>) => {
    try {
      setIsMoving(true);
      setDragError(null);
      await actionFn();
      await loadGroups(projectId);
      await useProjectStore.getState().loadProject(projectId);
      setSelectedGroupIds([]);
    } catch (err) {
      console.error("Action failed:", err);
      setDragError(err instanceof Error ? err.message : "操作失败，请重试");
    } finally {
      setIsMoving(false);
    }
  };

  const handleConfirmGroup = (groupId: string) => handleAction(() => confirmGroup(groupId, projectId));
  
  const handleMarkNotComparable = (groupId: string) => {
    setNotComparableConfirmGroup(groupId);
  };
  const doMarkNotComparable = (groupId: string) => handleAction(() => markNotComparable(groupId, projectId));

  const handleMergeSelected = () => {
    if (selectedGroupIds.length < 2) return;
    setMergeConfirmOpen(true);
  };
  const doMergeSelected = () => {
    if (selectedGroupIds.length < 2) return;
    handleAction(() => mergeGroups(projectId, selectedGroupIds));
  };

  const handleSplitSubmit = async (newGroups: string[][]) => {
    if (!splitDialogGroup) return;
    await handleAction(() => splitGroup(splitDialogGroup.id, projectId, newGroups));
    setSplitDialogGroup(null);
  };

  const handleDragStart = (event: DragStartEvent) => {
    setDragError(null);
    const { active } = event;
    if (active.data.current?.type === 'member') {
      setActiveDragItem(active.data.current as { member: GroupMemberSummary, sourceGroupId: string });
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragItem(null);

    if (!over) return;
    if (active.data.current?.type !== 'member') return;
    if (over.data.current?.type !== 'group') return;

    const sourceGroupId = active.data.current.sourceGroupId as string;
    const targetGroupId = over.id as string;
    const memberId = active.id as string;

    if (sourceGroupId === targetGroupId) return;
    if (!over.data.current.isDroppable) return;

    try {
      setIsMoving(true);
      await moveMember(sourceGroupId, projectId, targetGroupId, memberId);
      await loadGroups(projectId);
      await useProjectStore.getState().loadProject(projectId);
    } catch (err) {
      console.error("Failed to move member:", err);
      setDragError(err instanceof Error ? err.message : "拖拽移动成员失败，请重试");
    } finally {
      setIsMoving(false);
    }
  };

  const handleDragCancel = () => {
    setActiveDragItem(null);
  };

  useEffect(() => {
    loadGroups(projectId);
  }, [projectId, loadGroups]);

  if (isLoading) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
      </div>
    );
  }

  if (error || groups.length === 0) {
    return (
      <div className="flex h-[600px] items-center justify-center bg-white border border-slate-200 rounded-lg shadow-sm">
        <div className="text-center max-w-sm">
          <div className="mx-auto w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">{error ? "归组数据加载失败" : "尚未生成候选归组"}</h2>
          <p className="text-sm text-slate-500 mb-6 leading-relaxed">
            {error ? (
              <span className="text-red-500">{error}</span>
            ) : (
              "目前项目还没有归组数据。我们将基于规格型号、单位、名称等特征智能聚合相同或相近报价项。"
            )}
          </p>
          <Button 
            onClick={() => error ? loadGroups(projectId) : generateGrouping(projectId)} 
            disabled={isGenerating || isLoading}
            size="lg"
            className="w-full sm:w-auto font-medium shadow-sm bg-blue-600 hover:bg-blue-700"
          >
            {isGenerating ? "处理中..." : error ? "重试加载" : "开始智能归组"}
          </Button>
        </div>
      </div>
    );
  }

  const selectedGroup = groups.find(g => g.id === selectedGroupId);

  return (
    <DndContext collisionDetection={pointerWithin} onDragStart={handleDragStart} onDragEnd={handleDragEnd} onDragCancel={handleDragCancel}>
    <div className="flex h-[calc(100vh-140px)] gap-6 relative">
      {isMoving && (
        <div className="absolute inset-0 bg-white/40 backdrop-blur-[1px] z-[100] flex items-center justify-center rounded-lg">
          <div className="bg-white p-4 rounded-xl shadow-lg border border-slate-200 flex items-center gap-3">
            <div className="h-5 w-5 border-2 border-solid border-blue-600 border-r-transparent animate-spin rounded-full"></div>
            <span className="text-sm font-medium text-slate-700">正在移动数据...</span>
          </div>
        </div>
      )}
      {/* 左侧候选列表 */}
      <div className="w-[380px] flex-none flex flex-col h-full bg-slate-50 border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <div className="flex-none p-4 border-b border-slate-200 bg-white flex justify-between items-center shadow-sm z-10">
          <h3 className="font-semibold text-slate-900 text-sm flex items-center gap-2">
            候选归组列表
            <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">{groups.length} 组</span>
          </h3>
          <div className="flex items-center gap-2">
            {selectedGroupIds.length >= 2 && (
              <Button variant="default" size="sm" className="h-7 text-xs bg-blue-600 hover:bg-blue-700" onClick={handleMergeSelected} disabled={isMoving || isGenerating}>合并选中 ({selectedGroupIds.length})</Button>
            )}
            <Button variant="outline" size="sm" className="h-7 text-xs bg-white" onClick={() => generateGrouping(projectId)} disabled={isGenerating || isMoving}>重置</Button>
          </div>
        </div>
        <ScrollArea className="flex-1 p-4">
          <GroupCandidateList 
            groups={groups} 
            activeGroupId={selectedGroupId} 
            onSelectGroup={selectGroup} 
            selectedGroupIds={selectedGroupIds}
            onToggleGroupSelect={handleToggleGroupSelect}
            onConfirmGroup={handleConfirmGroup}
            onSplitGroup={setSplitDialogGroup}
            onMarkNotComparable={handleMarkNotComparable}
          />
        </ScrollArea>
      </div>

      {/* 右侧详情区 */}
      <div className="flex-1 flex flex-col h-full bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        {selectedGroup ? (
          <>
            <div className="flex-none p-6 border-b border-slate-100 bg-white z-10 shadow-sm flex justify-between items-start">
              <div>
                <h2 className="text-xl font-bold text-slate-900">{selectedGroup.groupName || "未命名归组"}</h2>
                <div className="text-sm text-slate-500 mt-1">标识键: <code className="bg-slate-100 px-1 py-0.5 rounded text-xs ml-1">{selectedGroup.normalizedKey}</code></div>
              </div>
            </div>
            {dragError && (
              <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  {dragError}
                </div>
                <button onClick={() => setDragError(null)} className="text-red-400 hover:text-red-600">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            )}
            <ScrollArea className="flex-1 bg-slate-50/50 p-6">
              <Card className="overflow-hidden border-slate-200 shadow-sm bg-white">
                <Table>
                  <TableHeader className="bg-slate-50">
                    <TableRow className="hover:bg-slate-50">
                      <TableHead className="w-[40px] px-2"></TableHead>
                      <TableHead className="w-[180px] font-semibold">供应商</TableHead>
                      <TableHead className="font-semibold">明细名称</TableHead>
                      <TableHead className="font-semibold">规格型号</TableHead>
                      <TableHead className="w-[80px] font-semibold">单位</TableHead>
                      <TableHead className="text-right w-[100px] font-semibold">数量</TableHead>
                      <TableHead className="text-right w-[120px] font-semibold">单价</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selectedGroup.members.map((member, idx) => (
                      <DraggableMemberRow 
                        key={member.standardizedRowId || idx} 
                        member={member} 
                        groupId={selectedGroup.id}
                        isDragDisabled={selectedGroup.members.length <= 1}
                      >
                        <TableCell className="font-medium text-slate-900">{member.supplierName}</TableCell>
                        <TableCell className="text-slate-700">{member.productName}</TableCell>
                        <TableCell className="text-slate-500 text-sm">{member.specModel || "-"}</TableCell>
                        <TableCell className="text-slate-500 text-sm">{member.unit || "-"}</TableCell>
                        <TableCell className="text-right text-slate-500 text-sm">{member.quantity !== null ? member.quantity : "-"}</TableCell>
                        <TableCell className="text-right font-medium text-slate-900">
                          {member.unitPrice !== null ? `¥${member.unitPrice.toFixed(2)}` : "-"}
                        </TableCell>
                      </DraggableMemberRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </ScrollArea>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-slate-400 p-8 text-center space-y-4 bg-slate-50/30">
            <div className="w-16 h-16 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-slate-600">未选择候选组</p>
              <p className="text-sm mt-1 max-w-[250px] mx-auto text-slate-400 leading-relaxed">请在左侧点击任一候选归组卡片，查看其包含的具体供应商报价项数据对比。</p>
            </div>
          </div>
        )}
      </div>
    </div>
    <DragOverlay zIndex={1000}>
      {activeDragItem ? (
        <div className="bg-white border border-blue-500 shadow-xl rounded-md p-3 w-[300px] flex flex-col gap-1 opacity-90 cursor-grabbing">
          <div className="font-medium text-slate-800 line-clamp-1 text-sm">{activeDragItem.member.supplierName}</div>
          <div className="text-xs text-slate-500 line-clamp-1">{activeDragItem.member.productName} - {activeDragItem.member.specModel}</div>
        </div>
      ) : null}
    </DragOverlay>
    <GroupSplitDialog 
      group={splitDialogGroup} 
      open={!!splitDialogGroup} 
      onClose={() => setSplitDialogGroup(null)} 
      onConfirm={handleSplitSubmit} 
    />
    <Dialog open={mergeConfirmOpen} onOpenChange={setMergeConfirmOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>合并候选归组</DialogTitle>
          <DialogDescription>
            将选中 {selectedGroupIds.length} 个候选组进行合并。合并后的新组将包含原有的所有明细成员。该操作无法直接撤销。您确定要合并吗？
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setMergeConfirmOpen(false)} disabled={isMoving}>取消</Button>
          <Button onClick={() => {
            setMergeConfirmOpen(false);
            doMergeSelected();
          }} disabled={isMoving}>确定合并</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <Dialog open={!!notComparableConfirmGroup} onOpenChange={(val) => !val && setNotComparableConfirmGroup(null)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>标记为不可比</DialogTitle>
          <DialogDescription>
            确定要将该商品归组标记为不可比吗？标记后，此归组将不再参与后续的比价计算流程，且需要手动恢复。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setNotComparableConfirmGroup(null)} disabled={isMoving}>取消</Button>
          <Button variant="destructive" onClick={() => {
            const groupId = notComparableConfirmGroup;
            setNotComparableConfirmGroup(null);
            if (groupId) doMarkNotComparable(groupId);
          }} disabled={isMoving}>确定标记</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </DndContext>
  );
}
