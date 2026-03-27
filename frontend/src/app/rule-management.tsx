import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ColumnMappingRule, ValueNormalizationRule } from "../types/rule";
import { useRuleStore } from "../stores/rule-store";
import { RuleList } from "../components/rules/rule-list";
import { RuleEditor } from "../components/rules/rule-editor";
import { RuleTestPanel } from "../components/rules/rule-test-panel";
import { ImportExportPanel } from "../components/rules/import-export-panel";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { Card } from "../components/ui/card";

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
    <div className="flex flex-col h-screen min-w-[1280px] bg-slate-50 font-sans overflow-hidden">
      <header className="flex-none h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm z-10 transition-colors">
        <div className="flex items-center gap-4">
          <Button 
            variant="ghost" size="sm"
            onClick={() => navigate("/")}
            className="text-slate-500 gap-2"
          >
            <span aria-hidden="true">&larr;</span> 返回首页
          </Button>
          <Separator orientation="vertical" className="h-4" />
          <h1 className="text-sm font-semibold text-slate-900 tracking-wide flex items-center gap-2">
            高级规则管理
          </h1>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden p-6 gap-6 max-w-[1600px] w-full mx-auto">
        <Card className="flex w-[400px] flex-col overflow-hidden shrink-0 border-slate-200 rounded-lg">
          <div className="flex-1 overflow-hidden flex flex-col">
            <RuleList onSelectRule={handleSelectRule} onNewRule={handleNewRule} />
          </div>
          <div className="border-t border-slate-100 bg-slate-50/50 p-2">
            <ImportExportPanel />
          </div>
        </Card>

        <Card className="flex-1 overflow-hidden flex flex-col relative border-slate-200 rounded-lg">
          {isEditing ? (
            <div className="flex-1 overflow-y-auto">
               <RuleEditor rule={selectedRule} onClose={handleCloseEditor} />
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
               <RuleTestPanel />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export default RuleManagement;
