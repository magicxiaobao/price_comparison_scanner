import { useState } from "react";

interface CreateProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}

function CreateProjectDialog({ open, onClose, onCreate }: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!open) return null;

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setLoading(true);
    setErrorMsg("");
    try {
      await onCreate(name.trim());
      setName("");
      onClose();
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      console.error("[CreateProject] error:", error);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
        <h2 className="text-lg font-semibold mb-4">新建项目</h2>
        <input
          type="text"
          className="w-full border rounded px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="请输入项目名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          autoFocus
        />
        {errorMsg && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm break-all">
            <strong>错误：</strong>{errorMsg}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button
            className="px-4 py-2 border rounded hover:bg-gray-100"
            onClick={onClose}
            disabled={loading}
          >
            取消
          </button>
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            onClick={handleSubmit}
            disabled={!name.trim() || loading}
          >
            {loading ? "创建中..." : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateProjectDialog;
