# Task 2.8: 前端 StandardizeStage — 预览 + 可编辑表格 + 手工修正

## 输入条件

- Task 2.5 完成（标准化 API + 手工修正 API 就绪）
- Task 2.9 完成或并行（RuleStore 就绪）
- Phase 0 前端骨架就绪（`components/stages/` 目录已存在）
- openapi.json 已包含标准化 API 定义

**⚠️ 前端首次使用 TanStack Table — 必须用 Context7 查文档确认用法。**

## 输出物

- 创建: `frontend/src/components/stages/standardize-stage.tsx`
- 创建: `frontend/src/components/stages/column-mapping-panel.tsx`
- 创建: `frontend/src/components/stages/standardized-data-table.tsx`
- 创建: `frontend/src/types/standardization.ts`
- 修改: `frontend/src/app/project-workbench.tsx`（集成 StandardizeStage 到工作台第二步）
- 修改: `frontend/src/lib/api.ts`（新增标准化相关 API 调用）

## 禁止修改

- 不修改 `backend/` 目录
- 不修改 `src/app/home-page.tsx`
- 不修改 `src/components/stages/` 中已有的 Phase 1 组件
- 不修改 `src/stores/project-store.ts` 的已有接口（可添加新 action）

## 实现规格

### types/standardization.ts

```typescript
export interface SourceLocationItem {
  type: "xlsx" | "docx" | "pdf" | "pdf_ocr";
  sheet?: string;
  cell?: string;
  tableIndex?: number;
  row?: number;
  col?: number;
  page?: number;
  extractionMode?: string;
  ocrConfidence?: number;
}

export type SourceLocation = Record<string, SourceLocationItem>;

export interface HitRuleSnapshot {
  ruleId: string;
  ruleName: string;
  matchContent: string;
  matchMode: string;
}

export interface StandardizedRow {
  id: string;
  rawTableId: string;
  supplierFileId: string;
  rowIndex: number;
  productName: string | null;
  specModel: string | null;
  unit: string | null;
  quantity: number | null;
  unitPrice: number | null;
  totalPrice: number | null;
  taxRate: string | null;
  deliveryPeriod: string | null;
  remark: string | null;
  sourceLocation: SourceLocation;
  columnMapping: Record<string, string> | null;
  hitRuleSnapshots: HitRuleSnapshot[] | null;
  confidence: number;
  isManuallyModified: boolean;
  needsReview: boolean;
  taxBasis: "known_inclusive" | "known_exclusive" | "unknown" | null;
}

export interface ColumnMappingInfo {
  originalColumn: string;
  targetField: string | null;
  matchedRule: string | null;
  matchMode: string | null;
  status: "confirmed" | "pending" | "unmapped" | "conflict";
}

export interface FieldModifyResponse {
  success: boolean;
  auditLog: {
    field: string;
    beforeValue: string;
    afterValue: string;
    timestamp: string;
  };
  dirtyStages: string[];
}
```

### components/stages/standardize-stage.tsx

**页面布局（PRD 7.2 标准化阶段原型）：**

```
┌─────────────────────────────────────────────────┐
│ 标准化                                          │
│                                                 │
│ 供应商选择：[供应商 A ▼]                         │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ 列名映射面板 (ColumnMappingPanel)            │ │
│ │ 原始列名  →  标准字段   命中规则   状态       │ │
│ │ ...                                         │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ 标准化预览表格 (StandardizedDataTable)        │ │
│ │ TanStack Table — 可编辑单元格                │ │
│ │ ...                                         │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [执行标准化] [保存映射到全局规则] [下一步→]      │
└─────────────────────────────────────────────────┘
```

**功能：**
- 顶部供应商选择下拉：切换查看不同供应商的标准化结果
- 「执行标准化」按钮：调用 `POST /api/projects/{id}/standardize` → 轮询任务进度
- 标准化完成后加载结果：调用 `GET /api/projects/{id}/standardized-rows`
- 阶段状态集成：标准化完成后更新 `normalize_status` → 刷新 ProjectStore

### components/stages/column-mapping-panel.tsx

**功能：**
- 展示当前供应商文件的列名映射关系
- 每行显示：原始列名 → 标准字段 | 命中规则 | 状态（已确认/待确认/未映射/冲突）
- 未映射列：提供下拉框手动选择标准字段
- 冲突列：显示冲突提示，提供手动选择
- 来源追溯：点击标准字段可查看 source_location 信息

### components/stages/standardized-data-table.tsx

**功能（TanStack Table 可编辑表格）：**
- **⚠️ 首次使用 TanStack Table — 必须用 Context7 查文档确认 API 用法**
- 列定义：9 个标准字段 + 供应商名 + 置信度 + 修改标记
- 可编辑单元格：双击进入编辑模式
  - 编辑完成后调用 `PUT /api/standardized-rows/{id}` 保存
  - 保存成功后单元格显示修改标记图标
  - 保存成功后触发 ProjectStore 刷新阶段状态（处理失效传播）
- 置信度列：低置信度（< 0.8）黄色高亮
- 需复核行：`needsReview=true` 时整行淡黄色背景
- 手动修改行：`isManuallyModified=true` 时单元格角标标记
- 必填字段缺失：空值高亮提示

### lib/api.ts 新增

```typescript
// 标准化 API
runStandardization(projectId: string, force?: boolean): Promise<{ taskId: string }>;
getStandardizedRows(projectId: string): Promise<StandardizedRow[]>;
modifyStandardizedRow(rowId: string, field: string, newValue: string | number | null): Promise<FieldModifyResponse>;
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

- [ ] 项目工作台 → 第二步标准化 → StandardizeStage 正确渲染
- [ ] 点击"执行标准化" → 显示进度 → 完成后加载结果
- [ ] 列名映射面板正确展示映射关系和状态
- [ ] 标准化预览表格正确展示 9 列标准字段
- [ ] 双击单元格 → 进入编辑模式 → 修改值 → 回车保存
- [ ] 保存成功后单元格显示修改标记
- [ ] 保存成功后下游阶段状态变为 dirty（通过 ProjectStore 反映）
- [ ] 低置信度行黄色高亮
- [ ] 必填字段缺失高亮提示
- [ ] 供应商切换正确过滤显示
- [ ] 「保存映射到全局规则」按钮（占位，可延后实现具体逻辑）

## 提交

```bash
git add frontend/src/components/stages/standardize-stage.tsx \
       frontend/src/components/stages/column-mapping-panel.tsx \
       frontend/src/components/stages/standardized-data-table.tsx \
       frontend/src/types/standardization.ts \
       frontend/src/app/project-workbench.tsx \
       frontend/src/lib/api.ts
git commit -m "Phase 2.8: 前端 StandardizeStage — 列名映射面板 + TanStack Table 可编辑表格 + 手工修正"
```
