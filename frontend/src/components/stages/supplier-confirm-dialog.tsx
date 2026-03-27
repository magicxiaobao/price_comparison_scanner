import { useEffect, useState } from "react";
import { confirmSupplier } from "../../lib/api";

interface SupplierConfirmDialogProps {
  open: boolean;
  fileId: string;
  projectId: string;
  suggestedName: string;
  originalFilename: string;
  onConfirm: (supplierName: string) => void;
  onClose: () => void;
}

export function SupplierConfirmDialog({
  open,
  fileId,
  projectId,
  suggestedName,
  originalFilename,
  onConfirm,
  onClose,
}: SupplierConfirmDialogProps) {
  const [name, setName] = useState(suggestedName);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(suggestedName);
  }, [suggestedName]);

  if (!open) return null;

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("供应商名称不能为空");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await confirmSupplier(fileId, trimmed, projectId);
      onConfirm(trimmed);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "确认失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h2 className="text-lg font-semibold text-gray-900">确认供应商名称</h2>
        <p className="mt-2 text-sm text-gray-500">
          文件: {originalFilename}
        </p>

        <div className="mt-4">
          <label htmlFor="supplier-name" className="block text-sm font-medium text-gray-700">
            供应商名称
          </label>
          <input
            id="supplier-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="请输入供应商名称"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && !submitting) handleSubmit();
            }}
          />
          {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !name.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "确认中..." : "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}
