# Task 2.9: 前端 RuleStore

## 输入条件

- Task 2.3 完成（规则管理 API 就绪）
- Task 2.10 完成（openapi.json 已更新，含规则 API 定义）
- Phase 0 前端骨架就绪（`stores/` 目录已存在）

## 输出物

- 创建: `frontend/src/types/rule.ts`
- 创建: `frontend/src/stores/rule-store.ts`

## 禁止修改

- 不修改 `backend/` 目录
- 不修改 `stores/project-store.ts`（已稳定）
- 不修改 `src/lib/api.ts` 的已有函数签名

## 实现规格

### stores/rule-store.ts

```typescript
import { create } from "zustand";
import type {
  RuleSet,
  ColumnMappingRule,
  ValueNormalizationRule,
  RuleCreateUpdate,
  TemplateInfo,
  RuleTestResult,
  RuleImportSummary,
} from "../types/rule";
import { api } from "../lib/api";

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
```

**设计要点：**

- 遵循技术架构 6.2 的 RuleStore 接口定义
- 所有写操作完成后自动 `loadRules()` 刷新状态
- 错误通过 `error` 字段暴露，由组件层处理展示
- `testRule` 不修改状态，直接返回结果
- Store hook 名遵循前端命名规范：`useRuleStore`

## 测试与验收

**前端门禁：**

```bash
cd frontend
pnpm lint                              # exit 0
pnpm tsc --noEmit                      # exit 0
```

**断言清单（TypeScript 编译级验证）：**

- `useRuleStore` 导出类型正确
- `RuleStore` 接口包含所有必需方法
- `loadRules` / `loadTemplates` 返回 `Promise<void>`
- `testRule` 返回 `Promise<RuleTestResult>`
- `importRules` 返回 `Promise<RuleImportSummary>`
- `exportRules` 返回 `Promise<Blob>`
- 所有 API 调用类型与 `lib/api.ts` 一致

## 提交

```bash
git add frontend/src/stores/rule-store.ts
git commit -m "Phase 2.9: 前端 RuleStore — Zustand 规则状态管理"
```
