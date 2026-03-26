# Task 4.9: 前端 ComparisonStage — 比价结果 + 异常高亮 + 导出

## 输入条件

- Task 4.5 完成（比价 API 可用）
- Task 4.6 完成（导出 API 可用）
- openapi.json 已更新（比价 + 导出 API 部分）

## 输出物

- 创建: `frontend/src/components/stages/comparison-stage.tsx`
- 创建: `frontend/src/components/stages/comparison-table.tsx`
- 创建: `frontend/src/components/stages/anomaly-highlight.tsx`
- 创建: `frontend/src/components/stages/export-button.tsx`
- 创建: `frontend/src/types/comparison.ts`
- 创建: `frontend/src/stores/comparison-store.ts`
- 修改: `frontend/src/lib/api.ts`（新增比价 + 导出 API 调用）
- 修改: `frontend/src/app/project-workbench.tsx`（接入 ComparisonStage）

## 禁止修改

- 不修改 `backend/`
- 不修改已有 stages 组件
- 不修改 `frontend/src/App.tsx` 路由配置

## 实现规格

**MCP 强制规则**：
- 实现前必须通过 openapi-contract MCP 工具查询比价和导出 API
- 首次使用 TanStack Table 列固定/列分组功能时，必须通过 Context7 查文档

### types/comparison.ts

```typescript
export interface SupplierPrice {
  supplier_file_id: string;
  supplier_name: string;
  unit_price: number | null;
  total_price: number | null;
  compliance_status?: string | null;
  is_acceptable?: boolean | null;
}

export interface AnomalyDetail {
  type: 'tax_basis_mismatch' | 'unit_mismatch' | 'currency_mismatch' | 'missing_required_field';
  description: string;
  blocking: boolean;
  affected_suppliers: string[];
}

export interface ComparisonResult {
  id: string;
  group_id: string;
  group_name: string;
  project_id: string;
  comparison_status: 'comparable' | 'blocked' | 'partial';
  supplier_prices: SupplierPrice[];
  min_price: number | null;
  effective_min_price: number | null;
  max_price: number | null;
  avg_price: number | null;
  price_diff: number | null;
  has_anomaly: boolean;
  anomaly_details: AnomalyDetail[];
  missing_suppliers: string[];
  generated_at: string;
}

export interface ExportResult {
  file_path: string;
  file_name: string;
  sheet_count: number;
}
```

### stores/comparison-store.ts

```typescript
import { create } from 'zustand';
import type { ComparisonResult } from '../types/comparison';

interface ComparisonStore {
  results: ComparisonResult[];
  isGenerating: boolean;
  isExporting: boolean;
  exportTaskId: string | null;
  isLoading: boolean;

  loadResults: (projectId: string) => Promise<void>;
  generateComparison: (projectId: string) => Promise<void>;
  exportReport: (projectId: string) => Promise<void>;
}
```

### 组件结构

#### comparison-stage.tsx
- 主容器
- 顶部操作栏：生成比价按钮 + 导出按钮
- 归组状态未完成时显示提示："请先完成商品归组"
- 比价结果为空时显示：点击"生成比价"按钮开始
- 有结果时显示 ComparisonTable

#### comparison-table.tsx（TanStack Table）
- 列结构：
  - 固定列：商品组名称、比较状态
  - 动态列：每个供应商一列（单价），根据实际供应商数量动态生成
  - 汇总列：全量最低价、有效最低价、最高价、平均价、差额
  - 标记列：异常标记
- 条件样式：
  - 全量最低价供应商单元格 → 绿色背景
  - 有效最低价供应商单元格 → 蓝色边框（若与全量最低价不同）
  - blocked 行 → 红色左边框
  - partial 行 → 黄色左边框
  - 缺项供应商 → 灰色斜线背景
- 行展开：点击行可展开查看异常详情

#### anomaly-highlight.tsx
- 异常行的内嵌组件
- 显示异常类型图标 + 异常描述文本
- 阻断异常（blocking）：红色感叹号
- 非阻断异常：黄色感叹号
- 鼠标悬停显示完整异常信息

#### export-button.tsx
- 导出按钮
- 点击后调用异步导出 API
- 显示导出进度（轮询 task status）
- 完成后提示下载路径
- 导出中禁用按钮

### api.ts 新增调用

```typescript
// 比价
generateComparison(projectId: string): Promise<{ task_id: string }>
getComparison(projectId: string): Promise<ComparisonResult[]>

// 导出
exportReport(projectId: string): Promise<{ task_id: string }>
```

## 测试与验收

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

**手动验证（需后端运行中）：**
- 工作台第五步显示"生成比价"按钮
- 点击生成比价 → 显示进度 → 完成后显示表格
- 表格动态列数与供应商数一致
- 全量最低价单元格绿色背景
- blocked 行有红色标识
- 异常行可展开查看详情
- 无需求标准时 effective_min == min（不显示蓝色边框）
- 导出按钮 → 进度 → 完成提示

**断言清单：**

| 断言 | 预期 |
|------|------|
| `pnpm lint` | exit 0 |
| `pnpm tsc --noEmit` | exit 0 |
| 生成比价 → 表格渲染 | 行数 == 商品组数 |
| 动态供应商列 | 列数正确 |
| 最低价高亮 | 绿色背景 |
| 异常行标识 | 红色/黄色 |
| 导出流程 | 进度 → 完成 |

## 提交

```bash
git add frontend/src/components/stages/comparison-stage.tsx \
       frontend/src/components/stages/comparison-table.tsx \
       frontend/src/components/stages/anomaly-highlight.tsx \
       frontend/src/components/stages/export-button.tsx \
       frontend/src/types/comparison.ts \
       frontend/src/stores/comparison-store.ts \
       frontend/src/lib/api.ts \
       frontend/src/app/project-workbench.tsx
git commit -m "Phase 4.9: ComparisonStage — TanStack Table 比价结果 + 异常高亮 + 导出按钮(异步)"
```
