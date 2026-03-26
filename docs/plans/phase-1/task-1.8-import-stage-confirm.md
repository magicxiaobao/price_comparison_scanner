# Task 1.8: 前端 ImportStage — 供应商确认 + 表格选择

## 输入条件

- Task 1.5 完成（供应商确认 API + 表格选择 API 就绪）
- Task 1.10 完成（openapi.json 已更新）
- Task 1.7 完成（ImportStage 容器 + 文件上传已就绪）

## 输出物

- 创建: `frontend/src/components/stages/supplier-confirm-dialog.tsx`
- 创建: `frontend/src/components/stages/table-selector.tsx`
- 修改: `frontend/src/components/stages/import-stage.tsx`（集成供应商确认和表格选择）
- 修改: `frontend/src/lib/api.ts`（新增供应商确认和表格选择 API 调用）

## 禁止修改

- 不修改 `backend/`
- 不修改 `frontend/src/app/home-page.tsx`
- 不修改 `frontend/src/components/stages/file-uploader.tsx`（已稳定）

## 实现规格

> **MCP 强制规则：** frontend-dev 实现 API 调用前**必须**先通过 openapi-contract MCP 工具查询接口定义。

### lib/api.ts 新增方法

```typescript
// 供应商确认
confirmSupplier: async (fileId: string, supplierName: string, projectId: string): Promise<{
  file_id: string;
  supplier_name: string;
  supplier_confirmed: boolean;
}> => {
  const resp = await axios.put(`/api/files/${fileId}/confirm-supplier`, {
    supplier_name: supplierName,
    project_id: projectId,
  });
  return resp.data;
},

// 表格选择
toggleTableSelection: async (tableId: string, projectId: string): Promise<{
  table_id: string;
  selected: boolean;
}> => {
  const resp = await axios.put(`/api/tables/${tableId}/toggle-selection`, {
    project_id: projectId,
  });
  return resp.data;
},
```

### components/stages/supplier-confirm-dialog.tsx

```typescript
interface SupplierConfirmDialogProps {
  open: boolean;
  fileId: string;
  projectId: string;
  suggestedName: string;           // 系统猜测的供应商名称
  originalFilename: string;
  onConfirm: (supplierName: string) => void;
  onClose: () => void;
}
```

**功能要点：**
- 对话框形式（使用基础 UI 组件）
- 显示文件名和猜测的供应商名称
- 输入框预填猜测名称，用户可修改
- 确认按钮调用 `api.confirmSupplier()`
- 确认成功后回调 `onConfirm`
- 供应商名称不能为空

### components/stages/table-selector.tsx

```typescript
interface TableSelectorProps {
  projectId: string;
  tables: RawTable[];
  onSelectionChange: (tableId: string, selected: boolean) => void;
}
```

**功能要点：**
- 按文件分组显示表格列表
- 每个表格显示：表格名称（sheet_name 或 "表格 N"）、行数、列数、所属供应商
- 复选框控制是否参与比价（默认选中）
- 点击复选框调用 `api.toggleTableSelection()`
- 可展开预览表格前 5 行数据（raw_data 的 headers + 前 5 行）

### import-stage.tsx 修改

在 ImportStage 中集成供应商确认和表格选择：

```typescript
// 解析完成后触发供应商确认流程
// 1. 文件上传 + 解析完成 → 自动弹出供应商确认对话框
// 2. 供应商确认后 → 下方显示该文件的表格列表（TableSelector）
// 3. 所有文件都已确认供应商 → 显示「确认完成，可进入下一步」提示
```

**交互流程：**
1. 用户上传文件 → 显示解析进度
2. 解析完成 → 如果供应商未确认，高亮提示「请确认供应商名称」
3. 用户点击文件行的「确认」按钮 → 弹出 SupplierConfirmDialog
4. 确认供应商后 → 展开该文件的表格列表
5. 用户可勾选/取消表格
6. 所有文件供应商已确认 → 底部显示汇总信息（N 个供应商，M 个表格参与比价）

## 测试与验收

### 门禁检查

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

### 手动验收

- 文件解析完成后 → 文件行显示「确认供应商」按钮
- 点击「确认供应商」→ 弹出对话框，预填猜测名称
- 修改名称后确认 → 供应商名称更新，按钮变为已确认状态
- 供应商确认后 → 展开表格列表
- 表格列表显示每个表格的 sheet_name/行数/列数
- 点击复选框 → 表格 selected 状态切换
- 展开表格可预览前 5 行数据
- 所有文件确认后 → 底部显示汇总

**断言清单：**
- `pnpm lint` → 退出码 0
- `pnpm tsc --noEmit` → 退出码 0
- SupplierConfirmDialog 禁止空供应商名称提交
- TableSelector 正确显示 selected 状态并可切换
- API 调用与 openapi.json 定义一致

## 提交

```bash
git add frontend/src/components/stages/supplier-confirm-dialog.tsx \
       frontend/src/components/stages/table-selector.tsx \
       frontend/src/components/stages/import-stage.tsx \
       frontend/src/lib/api.ts
git commit -m "Phase 1.8: 前端 ImportStage — 供应商确认对话框 + 表格选择列表"
```
