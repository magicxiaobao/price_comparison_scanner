import { create } from "zustand";
import type {
  RuleSet,
  RuleCreateUpdate,
  TemplateInfo,
  RuleTestResult,
  RuleImportSummary,
} from "../types/rule";
import * as api from "../lib/api";

interface RuleStore {
  // ---- 状态 ----
  rules: RuleSet | null;
  templates: TemplateInfo[];
  isLoading: boolean;
  error: string | null;

  // ---- 规则加载 ----
  loadRules: () => Promise<void>;
  loadTemplates: () => Promise<void>;

  // ---- 规则 CRUD ----
  upsertRule: (rule: RuleCreateUpdate) => Promise<void>;
  deleteRule: (ruleId: string) => Promise<void>;
  toggleRule: (ruleId: string) => Promise<void>;

  // ---- 模板和重置 ----
  loadTemplate: (templateId: string) => Promise<void>;
  resetDefault: () => Promise<void>;

  // ---- 导入导出 ----
  importRules: (file: File, strategy?: string) => Promise<RuleImportSummary>;
  exportRules: () => Promise<Blob>;

  // ---- 测试 ----
  testRule: (columnName: string, projectId?: string) => Promise<RuleTestResult>;

  // ---- 清理 ----
  clearError: () => void;
}

const useRuleStore = create<RuleStore>((set, get) => ({
  rules: null,
  templates: [],
  isLoading: false,
  error: null,

  loadRules: async () => {
    set({ isLoading: true, error: null });
    try {
      const rules = await api.getRules();
      set({ rules, isLoading: false });
    } catch (e) {
      set({ error: String(e), isLoading: false });
    }
  },

  loadTemplates: async () => {
    try {
      const templates = await api.getTemplates();
      set({ templates });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  upsertRule: async (rule) => {
    await api.upsertRule(rule);
    await get().loadRules();
  },

  deleteRule: async (ruleId) => {
    await api.deleteRule(ruleId);
    await get().loadRules();
  },

  toggleRule: async (ruleId) => {
    await api.toggleRule(ruleId);
    await get().loadRules();
  },

  loadTemplate: async (templateId) => {
    await api.loadTemplate(templateId);
    await get().loadRules();
  },

  resetDefault: async () => {
    await api.resetDefault();
    await get().loadRules();
  },

  importRules: async (file, strategy) => {
    const summary = await api.importRules(file, strategy);
    await get().loadRules();
    return summary;
  },

  exportRules: async () => {
    return api.exportRules();
  },

  testRule: async (columnName, projectId) => {
    return api.testRule(columnName, projectId);
  },

  clearError: () => set({ error: null }),
}));

export { useRuleStore };
export type { RuleStore };
