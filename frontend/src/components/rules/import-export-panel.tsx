import { useRef, useState } from "react";
import type { RuleImportSummary, TemplateInfo } from "../../types/rule";
import { useRuleStore } from "../../stores/rule-store";

export function ImportExportPanel() {
  const { templates, loadTemplates, loadTemplate, resetDefault, importRules, exportRules } =
    useRuleStore();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importStrategy, setImportStrategy] = useState("ask");
  const [importResult, setImportResult] = useState<RuleImportSummary | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const blob = await exportRules();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "rules-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出失败");
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async (file: File) => {
    setBusy(true);
    setError(null);
    setImportResult(null);
    try {
      const summary = await importRules(file, importStrategy);
      setImportResult(summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导入失败");
    } finally {
      setBusy(false);
    }
  };

  const handleShowTemplates = async () => {
    if (!showTemplates) {
      await loadTemplates();
    }
    setShowTemplates(!showTemplates);
  };

  const handleLoadTemplate = async (t: TemplateInfo) => {
    setBusy(true);
    setError(null);
    try {
      await loadTemplate(t.id);
      setShowTemplates(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载模板失败");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    setError(null);
    try {
      await resetDefault();
      setResetConfirm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复默认失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 border-t border-gray-200 px-4 py-3">
      {error && <p className="text-xs text-red-600">{error}</p>}

      {/* 导入导出 */}
      <div className="flex gap-2">
        <button
          onClick={handleExport}
          disabled={busy}
          className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          导出
        </button>
        <div className="flex flex-1 items-center gap-1">
          <select
            value={importStrategy}
            onChange={(e) => setImportStrategy(e.target.value)}
            className="w-20 rounded-md border border-gray-300 px-1 py-1.5 text-xs"
          >
            <option value="ask">默认</option>
            <option value="overwrite">覆盖</option>
            <option value="skip">跳过</option>
          </select>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={busy}
            className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            导入
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleImport(file);
              e.target.value = "";
            }}
          />
        </div>
      </div>

      {importResult && (
        <div className="rounded-md bg-green-50 px-3 py-2 text-xs text-green-800">
          导入完成: 新增 {importResult.added}, 冲突 {importResult.conflicts}, 跳过{" "}
          {importResult.skipped}, 共 {importResult.total}
        </div>
      )}

      {/* 模板和重置 */}
      <div className="flex gap-2">
        <button
          onClick={handleShowTemplates}
          disabled={busy}
          className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {showTemplates ? "收起模板" : "加载模板"}
        </button>
        {resetConfirm ? (
          <div className="flex flex-1 gap-1">
            <button
              onClick={handleReset}
              disabled={busy}
              className="flex-1 rounded-md bg-red-600 px-2 py-1.5 text-xs text-white disabled:opacity-50"
            >
              确认恢复
            </button>
            <button
              onClick={() => setResetConfirm(false)}
              className="flex-1 rounded-md border px-2 py-1.5 text-xs text-gray-600"
            >
              取消
            </button>
          </div>
        ) : (
          <button
            onClick={() => setResetConfirm(true)}
            disabled={busy}
            className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            恢复默认
          </button>
        )}
      </div>

      {showTemplates && (
        <div className="rounded-md border border-gray-200 bg-white">
          {templates.length === 0 ? (
            <p className="px-3 py-2 text-xs text-gray-400">无可用模板</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {templates.map((t) => (
                <li key={t.id} className="px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-gray-900">{t.name}</p>
                      <p className="text-xs text-gray-500">
                        {t.description} ({t.ruleCount} 条规则)
                      </p>
                    </div>
                    <button
                      onClick={() => handleLoadTemplate(t)}
                      disabled={busy}
                      className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      加载
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
