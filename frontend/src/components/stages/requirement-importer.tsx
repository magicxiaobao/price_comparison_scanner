import { useState, useRef } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../ui/dialog";
import { importRequirements, exportRequirements } from "../../lib/api";
import { useComplianceStore } from "../../stores/compliance-store";
import type { RequirementImportResult } from "../../types/compliance";

interface RequirementImporterProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
}

export function RequirementImporter({ projectId, open, onClose }: RequirementImporterProps) {
  const { loadRequirements } = useComplianceStore();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<RequirementImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.name.endsWith(".xlsx") && !file.name.endsWith(".xls")) {
      setError("请选择 .xlsx 格式的 Excel 文件");
      return;
    }
    setIsUploading(true);
    setError(null);
    setResult(null);
    try {
      const importResult = await importRequirements(projectId, file);
      setResult(importResult);
      await loadRequirements(projectId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导入失败");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleExportTemplate = async () => {
    try {
      const blob = await exportRequirements(projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "需求标准模板.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出模板失败");
    }
  };

  const handleClose = () => {
    setResult(null);
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>导入需求标准</DialogTitle>
          <DialogDescription>
            上传 Excel 文件批量导入需求项。列结构：分类、标题、描述、是否必选、判断类型、目标值、操作符。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Card
            className={`border-2 border-dashed p-8 text-center cursor-pointer transition-colors ${
              isDragging
                ? "border-blue-400 bg-blue-50"
                : "border-slate-200 hover:border-slate-300"
            }`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              onChange={handleFileSelect}
            />
            {isUploading ? (
              <div className="flex flex-col items-center gap-2">
                <div className="h-6 w-6 border-2 border-blue-600 border-r-transparent animate-spin rounded-full" />
                <p className="text-sm text-slate-500">正在导入...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-slate-600 font-medium">拖拽 Excel 文件到此处</p>
                <p className="text-xs text-slate-400">或点击选择文件（.xlsx）</p>
              </div>
            )}
          </Card>

          {result && (
            <div className="bg-green-50 border border-green-200 rounded-md p-3 space-y-1">
              <p className="text-sm font-medium text-green-800">导入完成</p>
              <div className="text-xs text-green-700 space-y-0.5">
                <p>总计: {result.total} 条 | 成功: {result.imported} 条 | 跳过: {result.skipped} 条</p>
                {result.errors.length > 0 && (
                  <div className="mt-2 space-y-0.5">
                    <p className="font-medium text-red-700">错误信息:</p>
                    {result.errors.map((err, i) => (
                      <p key={i} className="text-red-600">{err}</p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        <DialogFooter className="flex-row justify-between sm:justify-between">
          <Button variant="outline" size="sm" onClick={handleExportTemplate}>
            下载模板
          </Button>
          <Button variant="outline" onClick={handleClose}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
