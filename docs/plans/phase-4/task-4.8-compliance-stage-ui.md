# Task 4.8: 前端 ComplianceStage — 需求录入 + 符合性矩阵 + 证据面板

## 输入条件

- Task 4.3 完成（符合性 API 可用）
- openapi.json 已更新（需求标准 + 符合性 API 部分）
- 前端 API Client 封装可用（Phase 0 已建好）

## 输出物

- 创建: `frontend/src/components/stages/compliance-stage.tsx`
- 创建: `frontend/src/components/stages/requirement-editor.tsx`
- 创建: `frontend/src/components/stages/requirement-importer.tsx`
- 创建: `frontend/src/components/stages/compliance-matrix.tsx`
- 创建: `frontend/src/components/stages/evidence-detail-panel.tsx`
- 创建: `frontend/src/types/compliance.ts`
- 创建: `frontend/src/stores/compliance-store.ts`
- 修改: `frontend/src/lib/api.ts`（新增符合性相关 API 调用）
- 修改: `frontend/src/app/project-workbench.tsx`（接入 ComplianceStage）

## 禁止修改

- 不修改 `backend/`
- 不修改已有 stages 组件（import-stage, standardize-stage, grouping-stage）
- 不修改 `frontend/src/App.tsx` 路由配置

## 实现规格

**MCP 强制规则**：frontend-dev 实现前必须通过 openapi-contract MCP 工具查询接口定义，不可凭假设编码。

### types/compliance.ts

```typescript
export interface RequirementItem {
  id: string;
  project_id: string;
  code: string | null;
  category: '功能要求' | '技术规格' | '商务条款' | '服务要求' | '交付要求';
  title: string;
  description: string | null;
  is_mandatory: boolean;
  match_type: 'keyword' | 'numeric' | 'manual';
  expected_value: string | null;
  operator: 'gte' | 'lte' | 'eq' | 'range' | null;
  sort_order: number;
  created_at: string;
}

export interface RequirementCreate {
  code?: string;
  category: string;
  title: string;
  description?: string;
  is_mandatory?: boolean;
  match_type: string;
  expected_value?: string;
  operator?: string;
}

export interface ComplianceMatrixCell {
  match_id: string;
  status: 'match' | 'partial' | 'no_match' | 'unclear';
  is_acceptable: boolean;
  needs_review: boolean;
  evidence_text: string | null;
}

export interface ComplianceMatrixRow {
  requirement: RequirementItem;
  suppliers: Record<string, ComplianceMatrixCell>;
}

export interface ComplianceMatrix {
  supplier_names: Record<string, string>;
  rows: ComplianceMatrixRow[];
}

export interface RequirementImportResult {
  total: number;
  imported: number;
  skipped: number;
  errors: string[];
}
```

### stores/compliance-store.ts

```typescript
import { create } from 'zustand';
import type { RequirementItem, ComplianceMatrix } from '../types/compliance';

interface ComplianceStore {
  requirements: RequirementItem[];
  matrix: ComplianceMatrix | null;
  selectedMatchId: string | null;
  isEvaluating: boolean;
  isLoading: boolean;

  loadRequirements: (projectId: string) => Promise<void>;
  loadMatrix: (projectId: string) => Promise<void>;
  setSelectedMatch: (matchId: string | null) => void;
  setEvaluating: (evaluating: boolean) => void;
}
```

### 组件结构

#### compliance-stage.tsx
- 主容器，根据是否有需求项显示不同 UI
- 无需求项：引导页面（"录入需求标准"按钮 + "跳过此步骤"按钮）
- 有需求项：上半区 RequirementEditor，下半区 ComplianceMatrix + EvidenceDetailPanel
- 顶部操作栏：导入模板按钮 + 执行匹配按钮 + 导出模板按钮

#### requirement-editor.tsx
- 需求项列表（表格形式，支持内联编辑）
- 每行显示：编号、分类（下拉选择）、标题、是否必选（开关）、判断类型（下拉）、目标值、操作符
- 新增行按钮（底部）
- 删除按钮（每行末尾）
- 表单校验：title 必填，category 必须是枚举值，match_type 必须是枚举值

#### requirement-importer.tsx
- 文件上传区域（拖拽或点击选择 .xlsx 文件）
- 上传后显示导入结果（imported/skipped/errors）
- 模板下载链接

#### compliance-matrix.tsx
- 矩阵表格：横轴为供应商，纵轴为需求项
- 单元格颜色编码：
  - match → 绿色
  - partial → 黄色
  - no_match → 红色
  - unclear → 灰色
- 单元格点击 → 弹出确认对话框（可修改 status）
- partial 行显示「标记可接受」开关
- needs_review 行有待确认标记（闪烁或图标）

#### evidence-detail-panel.tsx
- 右侧或底部抽屉面板
- 显示选中匹配项的证据详情：
  - 证据原文
  - 来源位置
  - 匹配方式
  - 置信度
  - 确认状态
- 确认/修改按钮

### api.ts 新增调用

```typescript
// 需求标准
createRequirement(projectId: string, data: RequirementCreate): Promise<RequirementItem>
listRequirements(projectId: string): Promise<RequirementItem[]>
updateRequirement(reqId: string, data: Partial<RequirementCreate>): Promise<RequirementItem>
deleteRequirement(reqId: string): Promise<void>
importRequirements(projectId: string, file: File): Promise<RequirementImportResult>
exportRequirements(projectId: string): Promise<Blob>

// 符合性
evaluateCompliance(projectId: string): Promise<{ task_id: string }>
getComplianceMatrix(projectId: string): Promise<ComplianceMatrix>
confirmMatch(matchId: string, status: string): Promise<void>
acceptMatch(matchId: string, isAcceptable: boolean): Promise<void>
```

## 测试与验收

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

**手动验证（需后端运行中）：**
- 工作台第四步无需求时显示引导页
- 点击"录入需求标准" → 显示编辑表格
- 新增需求项 → 表格新增一行
- 编辑分类下拉、是否必选开关、判断类型下拉 → 正常保存
- 删除需求项 → 确认对话框 → 删除
- 导入 Excel 模板 → 显示导入结果
- 点击"执行匹配" → 显示进度 → 完成后显示矩阵
- 矩阵颜色编码正确（绿/黄/红/灰）
- 点击矩阵单元格 → 显示证据面板
- 确认匹配结果 → 单元格更新
- 标记可接受 → 单元格更新
- 跳过符合性审查 → 可直接进入第五步

**断言清单：**

| 断言 | 预期 |
|------|------|
| `pnpm lint` | exit 0 |
| `pnpm tsc --noEmit` | exit 0 |
| 无需求时显示引导 | 两个按钮可见 |
| 新增/编辑/删除需求 | CRUD 操作正常 |
| 导入 Excel | 显示统计结果 |
| 矩阵颜色编码 | 4 种状态 4 种颜色 |
| 证据面板 | 显示完整证据信息 |
| 确认/可接受操作 | API 调用成功 |

## 提交

```bash
git add frontend/src/components/stages/compliance-stage.tsx \
       frontend/src/components/stages/requirement-editor.tsx \
       frontend/src/components/stages/requirement-importer.tsx \
       frontend/src/components/stages/compliance-matrix.tsx \
       frontend/src/components/stages/evidence-detail-panel.tsx \
       frontend/src/types/compliance.ts \
       frontend/src/stores/compliance-store.ts \
       frontend/src/lib/api.ts \
       frontend/src/app/project-workbench.tsx
git commit -m "Phase 4.8: ComplianceStage — 需求录入表格 + 符合性矩阵(颜色编码) + 证据面板 + 导入导出"
```
