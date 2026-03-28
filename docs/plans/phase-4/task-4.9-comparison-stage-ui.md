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
// 注意：后端使用 _CAMEL_CONFIG，API JSON 字段名为 camelCase

export interface SupplierPrice {
  supplierFileId: string;
  supplierName: string;
  unitPrice: number | null;
  totalPrice: number | null;
  taxBasis?: string | null;        // [C12-fix] 与后端 SupplierPrice 模型对齐
  unit?: string | null;            // 单字段无需转换
  complianceStatus?: string | null;
  isAcceptable?: boolean | null;
}

export interface AnomalyDetail {
  type: 'tax_basis_mismatch' | 'unit_mismatch' | 'currency_mismatch' | 'missing_required_field';
  description: string;
  blocking: boolean;
  affectedSuppliers: string[];
}

export interface ComparisonResult {
  id: string;
  groupId: string;
  groupName: string;
  projectId: string;
  comparisonStatus: 'comparable' | 'blocked' | 'partial';
  supplierPrices: SupplierPrice[];
  minPrice: number | null;
  effectiveMinPrice: number | null;
  maxPrice: number | null;
  avgPrice: number | null;
  priceDiff: number | null;
  hasAnomaly: boolean;
  anomalyDetails: AnomalyDetail[];
  missingSuppliers: string[];
  generatedAt: string;
}

export interface ExportResult {
  filePath: string;
  fileName: string;
  sheetCount: number;
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
  exportTaskId: string | null;  // API 返回的 taskId
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

**[C10-fix] 列结构与固定范围：**
- 左侧固定列（`position: sticky; left: 0`，共 2 列，总宽 ~320px）：
  - 商品组名称（`minWidth: 200px`）
  - 比较状态（`minWidth: 120px`，badge 形式：comparable=绿色/blocked=红色/partial=黄色）
- 中间动态列（可横向滚动）：
  - 每个供应商一列（`minWidth: 140px`），列头显示供应商名称
  - 列顺序：按 `supplier_prices` 数组顺序（由后端保证按 supplier_file_id 排序）
- 右侧汇总列（共 6 列）：
  - 全量最低价、有效最低价、最高价、平均价、差额、异常标记
- 表格容器 `overflow-x: auto`，左侧固定列不随滚动

**[C10-fix] 条件样式与双口径高亮伪代码：**
```typescript
// 供应商单价单元格样式
function getSupplierCellClass(unitPrice: number | null, row: ComparisonResult): string {
  if (unitPrice === null) return 'bg-gray-100 bg-stripes';  // 缺项：灰色斜线背景
  const isMinPrice = unitPrice === row.minPrice;
  const isEffectiveMin = unitPrice === row.effectiveMinPrice;
  const effectiveDiffersFromMin = row.effectiveMinPrice !== null
    && row.effectiveMinPrice !== row.minPrice;

  if (isEffectiveMin && effectiveDiffersFromMin) {
    return 'ring-2 ring-blue-500 bg-blue-50';  // 有效最低价≠全量最低价 → 蓝色边框
  }
  if (isMinPrice) {
    return 'bg-green-100';  // 全量最低价 → 绿色背景
  }
  return '';
}

// 行样式
function getRowClass(row: ComparisonResult): string {
  if (row.comparisonStatus === 'blocked') return 'border-l-4 border-l-red-500';
  if (row.comparisonStatus === 'partial') return 'border-l-4 border-l-yellow-500';
  return '';
}
```

**注意：** 无需求标准时 `effective_min_price === min_price`，`effectiveDiffersFromMin` 为 false，不显示蓝色边框（正确行为）。

- 行展开：点击行可展开查看异常详情（展开状态用组件本地 `useState<Set<string>>` 管理，不存 store）

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
generateComparison(projectId: string): Promise<{ taskId: string }>
getComparison(projectId: string): Promise<ComparisonResult[]>

// 导出
exportReport(projectId: string): Promise<{ taskId: string }>
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

## Review Notes（审查发现的 Medium/Low 问题）

### 实现约束（开发时必须处理）

- **[M17] 导出进度轮询参数**：轮询间隔 2 秒，超时 300 秒，超时后显示"导出超时，请重试"。导出中不可取消（MVP 限制），按钮 disabled + spinner。
- **[M18] 供应商列顺序**：后端 ComparisonResultResponse.supplier_prices 按 supplier_file_id 排序（见 task-4.4 `sorted_sids`），前端按此顺序渲染列。列头显示 supplier_name。

### Reviewer 提醒

- **[M16] 行展开状态管理**：用组件本地 `useState<Set<string>>` 管理展开的行 ID 集合，不存入 store。
- **[Low] 空状态处理**：生成失败时显示 toast 错误提示（从 task status API 获取错误信息）。
- **[Low] 导出文件交付方式**：后端返回 file_path（服务器本地路径），Tauri 应用通过 Rust 端打开文件所在目录。开发模式下直接显示路径文本。
