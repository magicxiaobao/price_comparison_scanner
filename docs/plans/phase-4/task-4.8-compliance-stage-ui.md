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
// 注意：后端使用 _CAMEL_CONFIG，API JSON 字段名为 camelCase

export interface RequirementItem {
  id: string;
  projectId: string;
  code: string | null;
  category: '功能要求' | '技术规格' | '商务条款' | '服务要求' | '交付要求';
  title: string;
  description: string | null;
  isMandatory: boolean;
  matchType: 'keyword' | 'numeric' | 'manual';
  expectedValue: string | null;
  operator: 'gte' | 'lte' | 'eq' | 'range' | null;
  sortOrder: number;
  createdAt: string;
}

export interface RequirementCreate {
  code?: string;
  category: string;
  title: string;
  description?: string;
  isMandatory?: boolean;
  matchType: string;
  expectedValue?: string;
  operator?: string;
}

export interface ComplianceMatrixCell {
  matchId: string;
  status: 'match' | 'partial' | 'no_match' | 'unclear';
  isAcceptable: boolean;
  needsReview: boolean;
  evidenceText: string | null;
}

export interface ComplianceMatrixRow {
  requirement: RequirementItem;
  suppliers: Record<string, ComplianceMatrixCell>;
}

export interface ComplianceMatrix {
  supplierNames: Record<string, string>;
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
- 表单校验（[C9-fix] 完整 Zod schema）：
  ```typescript
  const requirementSchema = z.object({
    category: z.enum(['功能要求', '技术规格', '商务条款', '服务要求', '交付要求']),
    title: z.string().min(1, '标题不能为空').max(500),
    description: z.string().optional(),
    is_mandatory: z.boolean().default(true),
    match_type: z.enum(['keyword', 'numeric', 'manual']),
    expected_value: z.string().optional(),
    operator: z.enum(['gte', 'lte', 'eq', 'range']).optional(),
  }).refine(
    (data) => {
      // numeric 类型必须有 expected_value（数字格式）和 operator
      if (data.match_type === 'numeric') {
        if (!data.expected_value || !/^[\d.]+(-[\d.]+)?$/.test(data.expected_value)) return false;
        if (!data.operator) return false;
      }
      // keyword 类型必须有 expected_value（关键词）
      if (data.match_type === 'keyword' && !data.expected_value) return false;
      return true;
    },
    { message: '请根据判断类型填写完整的目标值和操作符' }
  );
  ```

#### requirement-importer.tsx
- 文件上传区域（拖拽或点击选择 .xlsx 文件）
- 上传后显示导入结果（imported/skipped/errors）
- 模板下载链接

#### compliance-matrix.tsx
- 矩阵表格：横轴为供应商，纵轴为需求项
- 单元格颜色编码（[C8-fix] 明确 Tailwind 类名）：
  - match → `bg-green-100 text-green-800 border-green-300`
  - partial → `bg-yellow-100 text-yellow-800 border-yellow-300`
  - no_match → `bg-red-100 text-red-800 border-red-300`
  - unclear → `bg-gray-100 text-gray-500 border-gray-300`
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
evaluateCompliance(projectId: string): Promise<{ taskId: string }>
getComplianceMatrix(projectId: string): Promise<ComplianceMatrix>
confirmMatch(matchId: string, projectId: string, status: string): Promise<void>   // body: { projectId, status }
acceptMatch(matchId: string, projectId: string, isAcceptable: boolean): Promise<void>  // body: { projectId, isAcceptable }
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

## Review Notes（审查发现的 Medium/Low 问题）

### 实现约束（开发时必须处理）

- **[M13] 矩阵交互流程明确**：单元格点击 → 打开右侧 EvidenceDetailPanel（显示证据+确认按钮）；行级别不做展开。状态修改（confirm/accept）在证据面板中操作，不在矩阵单元格上直接修改。
- **[M14] 证据面板数据来源**：所有证据字段（evidence_text, evidence_location, match_method, match_score, needs_review）来自后端 GET /compliance/matrix 响应中的 ComplianceMatrixCell。若需要更完整的证据，可通过 match_id 查询单条记录。
- **[M15] 需求导入 Excel 模板列结构**：列顺序为 `[分类, 标题, 描述, 是否必选, 判断类型, 目标值, 操作符]`。导入时按表头匹配（不依赖列序号）。「导出模板」功能会生成带表头的空模板 + 1 行示例数据。
- **[M13 补充] `confirmMatch` / `acceptMatch` API 调用需带 project_id**：请求体格式为 `{ project_id, status }` 和 `{ project_id, is_acceptable }`。

### Reviewer 提醒

- **[Low] 需求项拖拽排序不在 Phase 4 范围**：sort_order 字段由后端自动递增，前端不提供拖拽排序。后续版本可实现。
- **[Low] 导入错误信息格式**：errors 数组元素为纯文本字符串（如 "第3行: 分类无效"），包含行号和错误原因。
