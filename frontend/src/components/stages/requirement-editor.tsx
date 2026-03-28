import { useState } from "react";
import { z } from "zod";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Card } from "../ui/card";
import { ScrollArea } from "../ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../ui/dialog";
import { useComplianceStore } from "../../stores/compliance-store";
import type { RequirementItem, RequirementCreate, RequirementUpdate } from "../../types/compliance";
import { CATEGORY_OPTIONS, MATCH_TYPE_OPTIONS, OPERATOR_OPTIONS } from "../../types/compliance";

const requirementSchema = z
  .object({
    category: z.enum(["功能要求", "技术规格", "商务条款", "服务要求", "交付要求"]),
    title: z.string().min(1, "标题不能为空").max(500),
    description: z.string().optional(),
    isMandatory: z.boolean().default(true),
    matchType: z.enum(["keyword", "numeric", "manual"]),
    expectedValue: z.string().optional(),
    operator: z.enum(["gte", "lte", "eq", "range"]).optional(),
  })
  .refine(
    (data) => {
      if (data.matchType === "numeric") {
        if (!data.expectedValue || !/^[\d.]+(-[\d.]+)?$/.test(data.expectedValue)) return false;
        if (!data.operator) return false;
      }
      if (data.matchType === "keyword" && !data.expectedValue) return false;
      return true;
    },
    { message: "请根据判断类型填写完整的目标值和操作符" },
  );

interface RequirementEditorProps {
  projectId: string;
}

interface EditingRow {
  category: string;
  title: string;
  description: string;
  isMandatory: boolean;
  matchType: string;
  expectedValue: string;
  operator: string;
}

const EMPTY_ROW: EditingRow = {
  category: "功能要求",
  title: "",
  description: "",
  isMandatory: true,
  matchType: "keyword",
  expectedValue: "",
  operator: "",
};

export function RequirementEditor({ projectId }: RequirementEditorProps) {
  const { requirements, addRequirement, editRequirement, removeRequirement } = useComplianceStore();
  const [isAdding, setIsAdding] = useState(false);
  const [newRow, setNewRow] = useState<EditingRow>({ ...EMPTY_ROW });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingRow, setEditingRow] = useState<EditingRow>({ ...EMPTY_ROW });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const toCreatePayload = (row: EditingRow): RequirementCreate => ({
    category: row.category,
    title: row.title,
    description: row.description || undefined,
    isMandatory: row.isMandatory,
    matchType: row.matchType,
    expectedValue: row.expectedValue || undefined,
    operator: row.operator || undefined,
  });

  const toUpdatePayload = (row: EditingRow): RequirementUpdate => ({
    projectId,
    category: row.category,
    title: row.title,
    description: row.description || null,
    isMandatory: row.isMandatory,
    matchType: row.matchType,
    expectedValue: row.expectedValue || null,
    operator: row.operator || null,
  });

  const validateRow = (row: EditingRow): boolean => {
    const result = requirementSchema.safeParse(row);
    if (!result.success) {
      setValidationError(result.error.errors[0]?.message || "表单校验失败");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const handleAddRow = async () => {
    if (!validateRow(newRow)) return;
    await addRequirement(projectId, toCreatePayload(newRow));
    setNewRow({ ...EMPTY_ROW });
    setIsAdding(false);
    setValidationError(null);
  };

  const handleStartEdit = (req: RequirementItem) => {
    setEditingId(req.id);
    setEditingRow({
      category: req.category,
      title: req.title,
      description: req.description || "",
      isMandatory: req.isMandatory,
      matchType: req.matchType,
      expectedValue: req.expectedValue || "",
      operator: req.operator || "",
    });
    setValidationError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;
    if (!validateRow(editingRow)) return;
    await editRequirement(editingId, toUpdatePayload(editingRow));
    setEditingId(null);
    setValidationError(null);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setValidationError(null);
  };

  const handleDelete = async () => {
    if (!deleteConfirmId) return;
    await removeRequirement(deleteConfirmId, projectId);
    setDeleteConfirmId(null);
  };

  const renderEditableRow = (row: EditingRow, setRow: (r: EditingRow) => void, isNew: boolean) => (
    <TableRow className="bg-blue-50/30">
      <TableCell className="w-[60px] text-center text-xs text-slate-400">
        {isNew ? "+" : ""}
      </TableCell>
      <TableCell className="w-[120px]">
        <Select value={row.category} onValueChange={(v) => setRow({ ...row, category: v })}>
          <SelectTrigger className="h-8 text-xs w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        <Input
          value={row.title}
          onChange={(e) => setRow({ ...row, title: e.target.value })}
          placeholder="需求标题"
          className="h-8 text-sm"
        />
      </TableCell>
      <TableCell className="w-[60px] text-center">
        <button
          type="button"
          className={`w-5 h-5 rounded border text-xs font-bold transition-colors ${
            row.isMandatory
              ? "bg-blue-600 border-blue-600 text-white"
              : "bg-white border-slate-300 text-slate-400"
          }`}
          onClick={() => setRow({ ...row, isMandatory: !row.isMandatory })}
        >
          {row.isMandatory ? "M" : "O"}
        </button>
      </TableCell>
      <TableCell className="w-[100px]">
        <Select value={row.matchType} onValueChange={(v) => setRow({ ...row, matchType: v })}>
          <SelectTrigger className="h-8 text-xs w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MATCH_TYPE_OPTIONS.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell className="w-[120px]">
        <Input
          value={row.expectedValue}
          onChange={(e) => setRow({ ...row, expectedValue: e.target.value })}
          placeholder={row.matchType === "numeric" ? "数值/区间" : "关键词"}
          className="h-8 text-xs"
          disabled={row.matchType === "manual"}
        />
      </TableCell>
      <TableCell className="w-[80px]">
        {row.matchType === "numeric" ? (
          <Select value={row.operator} onValueChange={(v) => setRow({ ...row, operator: v })}>
            <SelectTrigger className="h-8 text-xs w-full">
              <SelectValue placeholder="���作符" />
            </SelectTrigger>
            <SelectContent>
              {OPERATOR_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <span className="text-xs text-slate-400">-</span>
        )}
      </TableCell>
      <TableCell className="w-[100px]">
        <div className="flex gap-1">
          <Button
            size="sm"
            className="h-7 text-xs"
            onClick={isNew ? handleAddRow : handleSaveEdit}
          >
            保存
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={isNew ? () => { setIsAdding(false); setValidationError(null); } : handleCancelEdit}
          >
            取消
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">
          需求项列表
          <span className="ml-2 text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
            {requirements.length} 项
          </span>
        </h3>
        {!isAdding && (
          <Button size="sm" className="h-7 text-xs" onClick={() => setIsAdding(true)}>
            新增需求
          </Button>
        )}
      </div>

      {validationError && (
        <div className="p-2 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
          {validationError}
        </div>
      )}

      <Card className="overflow-hidden border-slate-200">
        <ScrollArea className="max-h-[400px]">
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow className="hover:bg-slate-50">
                <TableHead className="w-[60px] text-center">#</TableHead>
                <TableHead className="w-[120px]">分类</TableHead>
                <TableHead>标题</TableHead>
                <TableHead className="w-[60px] text-center">必选</TableHead>
                <TableHead className="w-[100px]">判断类型</TableHead>
                <TableHead className="w-[120px]">目标值</TableHead>
                <TableHead className="w-[80px]">操作符</TableHead>
                <TableHead className="w-[100px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {requirements.map((req, idx) =>
                editingId === req.id ? (
                  renderEditableRow(editingRow, setEditingRow, false)
                ) : (
                  <TableRow key={req.id} className="hover:bg-slate-50/50">
                    <TableCell className="w-[60px] text-center text-xs text-slate-400">
                      {req.code || idx + 1}
                    </TableCell>
                    <TableCell className="text-xs">{req.category}</TableCell>
                    <TableCell className="text-sm font-medium text-slate-800">{req.title}</TableCell>
                    <TableCell className="text-center">
                      <span
                        className={`inline-block w-5 h-5 rounded text-xs font-bold leading-5 text-center ${
                          req.isMandatory
                            ? "bg-blue-100 text-blue-700"
                            : "bg-slate-100 text-slate-400"
                        }`}
                      >
                        {req.isMandatory ? "M" : "O"}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-slate-600">
                      {MATCH_TYPE_OPTIONS.find((m) => m.value === req.matchType)?.label || req.matchType}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">
                      {req.expectedValue || "-"}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">
                      {req.operator
                        ? OPERATOR_OPTIONS.find((o) => o.value === req.operator)?.label || req.operator
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-6 text-xs px-2"
                          onClick={() => handleStartEdit(req)}
                        >
                          编辑
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-6 text-xs px-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={() => setDeleteConfirmId(req.id)}
                        >
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ),
              )}
              {isAdding && renderEditableRow(newRow, setNewRow, true)}
              {requirements.length === 0 && !isAdding && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-sm text-slate-400 py-8">
                    暂无需求项，点击「新增需求」添加
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </Card>

      <Dialog open={!!deleteConfirmId} onOpenChange={(val) => !val && setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除需求项</DialogTitle>
            <DialogDescription>确定要删除此需求项吗？删除后不可恢复。</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              确定删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
