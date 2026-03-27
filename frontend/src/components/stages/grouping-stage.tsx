import { useEffect } from "react";
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
    <div className="flex h-[calc(100vh-140px)] gap-6">
      {/* 左侧候选列表 */}
      <div className="w-[380px] flex-none flex flex-col h-full bg-slate-50 border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <div className="flex-none p-4 border-b border-slate-200 bg-white flex justify-between items-center shadow-sm z-10">
          <h3 className="font-semibold text-slate-900 text-sm flex items-center gap-2">
            候选归组列表
            <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">{groups.length} 组</span>
          </h3>
          <Button variant="outline" size="sm" className="h-7 text-xs bg-white" onClick={() => generateGrouping(projectId)} disabled={isGenerating}>重置</Button>
        </div>
        <ScrollArea className="flex-1 p-4">
          <GroupCandidateList 
            groups={groups} 
            activeGroupId={selectedGroupId} 
            onSelectGroup={selectGroup} 
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
              <Button size="sm" variant="default" className="shadow-sm">一键确认全组</Button>
            </div>
            <ScrollArea className="flex-1 bg-slate-50/50 p-6">
              <Card className="overflow-hidden border-slate-200 shadow-sm bg-white">
                <Table>
                  <TableHeader className="bg-slate-50">
                    <TableRow className="hover:bg-slate-50">
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
                      <TableRow key={member.standardizedRowId || idx}>
                        <TableCell className="font-medium text-slate-900">{member.supplierName}</TableCell>
                        <TableCell className="text-slate-700">{member.productName}</TableCell>
                        <TableCell className="text-slate-500 text-sm">{member.specModel || "-"}</TableCell>
                        <TableCell className="text-slate-500 text-sm">{member.unit || "-"}</TableCell>
                        <TableCell className="text-right text-slate-500 text-sm">{member.quantity !== null ? member.quantity : "-"}</TableCell>
                        <TableCell className="text-right font-medium text-slate-900">
                          {member.unitPrice !== null ? `¥${member.unitPrice.toFixed(2)}` : "-"}
                        </TableCell>
                      </TableRow>
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
  );
}
