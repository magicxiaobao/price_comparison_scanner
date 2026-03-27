import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ColumnMappingRule, ValueNormalizationRule } from "../types/rule";
import { useRuleStore } from "../stores/rule-store";
import { RuleList } from "../components/rules/rule-list";
import { RuleEditor } from "../components/rules/rule-editor";
import { RuleTestPanel } from "../components/rules/rule-test-panel";
import { ImportExportPanel } from "../components/rules/import-export-panel";

type SelectedRule = ColumnMappingRule | ValueNormalizationRule;

function RuleManagement() {
  const navigate = useNavigate();
  const { loadRules } = useRuleStore();

  const [selectedRule, setSelectedRule] = useState<SelectedRule | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const handleSelectRule = (rule: SelectedRule) => {
    setSelectedRule(rule);
    setIsEditing(true);
  };

  const handleNewRule = () => {
    setSelectedRule(null);
    setIsEditing(true);
  };

  const handleCloseEditor = () => {
    setSelectedRule(null);
    setIsEditing(false);
  };

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* 顶部标题栏 */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-xl font-bold text-gray-900">规则管理</h1>
        <button
          onClick={() => navigate("/")}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          返回首页
        </button>
      </header>

      {/* 主体 2 列布局 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左栏: 规则列表 + 导入导出 */}
        <div className="flex w-1/2 flex-col border-r border-gray-200 bg-white">
          <div className="flex-1 overflow-hidden">
            <RuleList onSelectRule={handleSelectRule} onNewRule={handleNewRule} />
          </div>
          <ImportExportPanel />
        </div>

        {/* 右栏: 编辑器或测试面板 */}
        <div className="w-1/2 bg-white">
          {isEditing ? (
            <RuleEditor rule={selectedRule} onClose={handleCloseEditor} />
          ) : (
            <RuleTestPanel />
          )}
        </div>
      </div>
    </div>
  );
}

export default RuleManagement;
