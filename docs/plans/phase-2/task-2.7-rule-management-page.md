# Task 2.7: 前端 RuleManagement 页面

## 输入条件

- Task 2.3 完成（规则管理 API 10 个端点就绪）
- Task 2.9 完成或并行（RuleStore 就绪）
- Phase 0 前端骨架就绪（`app/rule-management.tsx` 占位页面已存在）
- openapi.json 已包含规则 API 定义

**前端首次使用 TanStack Table — 若此页面涉及表格展示，必须用 Context7 查文档确认用法。**

## 输出物

- 修改: `frontend/src/app/rule-management.tsx`（填充占位）
- 创建: `frontend/src/components/rules/rule-list.tsx`
- 创建: `frontend/src/components/rules/rule-editor.tsx`
- 创建: `frontend/src/components/rules/rule-test-panel.tsx`
- 创建: `frontend/src/components/rules/import-export-panel.tsx`
- 创建: `frontend/src/types/rule.ts`

## 禁止修改

- 不修改 `backend/` 目录
- 不修改 `src/app/home-page.tsx`（已稳定）
- 不修改 `src/lib/api.ts` 的已有函数签名（可添加新函数）
- 不修改 `src/stores/project-store.ts`

## 实现规格

### types/rule.ts

```typescript
export type MatchMode = "exact" | "fuzzy" | "regex";
export type RuleType = "column_mapping" | "value_normalization";

export interface ColumnMappingRule {
  id: string;
  enabled: boolean;
  type: RuleType;
  sourceKeywords: string[];
  targetField: string;
  matchMode: MatchMode;
  priority: number;
  createdAt: string;
}

export interface ValueNormalizationRule {
  id: string;
  type: RuleType;
  field: string;
  patterns: string[];
  replaceWith: string;
  createdAt: string;
}

export interface RuleSet {
  version: string;
  lastUpdated: string;
  columnMappingRules: ColumnMappingRule[];
  valueNormalizationRules: ValueNormalizationRule[];
}

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  ruleCount: number;
}

export interface RuleTestResult {
  matched: boolean;
  targetField: string | null;
  matchedRule: Record<string, unknown> | null;
  conflicts: Record<string, unknown>[];
  resolution: string | null;
}

export interface RuleImportSummary {
  total: number;
  added: number;
  conflicts: number;
  skipped: number;
}
```

### app/rule-management.tsx

```tsx
// 页面布局（PRD 7.1 + 技术架构 6.1）
// ┌─────────────────────────────────────────────┐
// │ 规则管理                          [返回首页] │
// ├──────────────────────┬──────────────────────┤
// │ 规则列表              │ 规则编辑器 / 测试面板 │
// │ - 列名映射规则        │ (选中规则时显示编辑器) │
// │ - 值标准化规则        │ (未选中时显示测试面板) │
// │                      │                      │
// │ [新增] [导入] [导出]  │                      │
// │ [加载模板] [恢复默认]  │                      │
// └──────────────────────┴──────────────────────┘
```

### components/rules/rule-list.tsx

**功能：**
- 展示列名映射规则和值标准化规则列表
- 每条规则显示：关键词、目标字段、匹配方式、启用状态
- 支持启用/停用切换（调用 `PUT /api/rules/{id}/toggle`）
- 支持删除（调用 `DELETE /api/rules/{id}`，需确认对话框）
- 点击规则进入编辑模式
- 底部操作按钮：新增、导入、导出、加载模板、恢复默认

### components/rules/rule-editor.tsx

**功能：**
- 新增/编辑规则的表单
- 列名映射规则表单字段：
  - 关键词列表（可多个，逗号分隔或标签输入）
  - 目标字段（下拉选择 9 个标准字段）
  - 匹配方式（exact / fuzzy / regex）
  - 优先级（数字输入）
- 值标准化规则表单字段：
  - 适用字段（下拉选择）
  - 模式列表（需替换的文本列表）
  - 替换为（目标文本）
- 保存按钮调用 `PUT /api/rules`
- 取消按钮返回列表

### components/rules/rule-test-panel.tsx

**功能（PRD 6.4 最小规则测试能力）：**
- 输入框：用户输入测试列名（如"报价含税"）
- 实时调用 `POST /api/rules/test`（防抖 300ms）
- 显示结果：
  - 匹配成功：显示目标字段 + 命中规则信息
  - 有冲突：显示冲突规则列表 + 优先级裁决结果
  - 未匹配：提示"未匹配任何规则"

### components/rules/import-export-panel.tsx

**功能：**
- 导出按钮：调用 `GET /api/rules/export`，下载 JSON 文件
- 导入按钮：选择 JSON 文件 → 调用 `POST /api/rules/import`
  - 导入前可选策略：覆盖全部 / 跳过全部
  - 导入后显示汇总：新增 N 条、覆盖 N 条、跳过 N 条
- 加载模板：调用 `GET /api/rules/templates` 获取列表 → 选择后调用 `POST /api/rules/load-template`
- 恢复默认：调用 `POST /api/rules/reset-default`（需确认对话框）

### lib/api.ts 新增

```typescript
// 规则管理 API
getRules(): Promise<RuleSet>;
getTemplates(): Promise<TemplateInfo[]>;
loadTemplate(templateId: string): Promise<RuleSet>;
upsertRule(rule: Partial<ColumnMappingRule | ValueNormalizationRule>): Promise<unknown>;
deleteRule(ruleId: string): Promise<void>;
toggleRule(ruleId: string): Promise<{ enabled: boolean }>;
importRules(file: File, strategy?: string): Promise<RuleImportSummary>;
exportRules(): Promise<Blob>;
resetDefault(): Promise<RuleSet>;
testRule(columnName: string, projectId?: string): Promise<RuleTestResult>;
```

**⚠️ 实现 API 调用前必须先通过 MCP 工具（openapi-contract）查询接口定义，不可凭假设编码。**

## 测试与验收

**前端门禁：**

```bash
cd frontend
pnpm lint                              # exit 0
pnpm tsc --noEmit                      # exit 0
```

**手动验证清单：**

- [ ] 导航到 `#/rules` 显示规则管理页面
- [ ] 规则列表正确展示列名映射规则和值标准化规则
- [ ] 新增列名映射规则：输入关键词 + 选择目标字段 + 选择匹配方式 → 保存成功 → 列表更新
- [ ] 编辑规则：点击规则 → 表单填充已有值 → 修改后保存
- [ ] 删除规则：点击删除 → 确认对话框 → 删除成功
- [ ] 启用/停用切换：开关切换 → API 调用成功 → 状态更新
- [ ] 规则测试：输入"单价" → 显示映射到 unit_price
- [ ] 规则测试冲突：输入有冲突的列名 → 显示冲突规则列表
- [ ] 导出规则：下载 JSON 文件，内容与当前规则一致
- [ ] 导入规则：选择 JSON 文件 → 显示导入结果汇总
- [ ] 加载模板：选择模板 → 规则列表更新
- [ ] 恢复默认：确认后规则恢复为内置模板

## 提交

```bash
git add frontend/src/app/rule-management.tsx \
       frontend/src/components/rules/ \
       frontend/src/types/rule.ts \
       frontend/src/lib/api.ts
git commit -m "Phase 2.7: 前端规则管理页面 — 规则 CRUD/测试/导入导出/模板管理"
```
