# Task 1.7: 前端 ImportStage — 文件上传 + 解析进度

## 输入条件

- Task 1.5 完成（文件导入 API 就绪）
- Task 1.10 完成（openapi.json 已更新）
- Phase 0 前端骨架就绪（路由、API Client、ProjectStore）

## 输出物

- 创建: `frontend/src/components/stages/import-stage.tsx`
- 创建: `frontend/src/components/stages/file-uploader.tsx`
- 创建: `frontend/src/types/file.ts`
- 创建: `frontend/src/types/task.ts`
- 修改: `frontend/src/lib/api.ts`（新增文件导入相关 API 调用）
- 修改: `frontend/src/app/project-workbench.tsx`（集成 ImportStage）

## 禁止修改

- 不修改 `backend/`
- 不修改 `frontend/src/app/home-page.tsx`
- 不修改 `frontend/src/stores/project-store.ts`（→ Task 1.9）

## 实现规格

> **MCP 强制规则：** frontend-dev 实现 API 调用前**必须**先通过 openapi-contract MCP 工具查询接口定义，不可凭假设编码。

### types/file.ts

```typescript
export interface SupplierFile {
  id: string;
  project_id: string;
  supplier_name: string;
  supplier_confirmed: boolean;
  original_filename: string;
  file_path: string;
  file_type: 'xlsx' | 'docx' | 'pdf' | 'image'; // image: Phase 5 OCR 模块支持，当前阶段上传器不接受
  recognition_mode: 'structure' | 'ocr' | 'manual' | null;
  imported_at: string;
}

export interface RawTable {
  id: string;
  supplier_file_id: string;
  table_index: number;
  sheet_name: string | null;
  page_number: number | null;
  row_count: number;
  column_count: number;
  raw_data: {
    headers: string[];
    rows: (string | null)[][];
  };
  selected: boolean;
  supplier_name?: string;
  original_filename?: string;
  supplier_confirmed?: boolean;
}

export interface FileUploadResponse {
  file_id: string;
  task_id: string;
  supplier_name_guess: string;
}
```

### types/task.ts

```typescript
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface TaskInfo {
  task_id: string;
  task_type: string;
  status: TaskStatus;
  progress: number;   // 0.0 - 1.0
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
```

### lib/api.ts 新增方法

```typescript
// 文件导入
uploadFile: async (projectId: string, file: File): Promise<FileUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const resp = await axios.post(`/api/projects/${projectId}/files`, formData);
  return resp.data;
},

listFiles: async (projectId: string): Promise<SupplierFile[]> => {
  const resp = await axios.get(`/api/projects/${projectId}/files`);
  return resp.data;
},

// 任务状态
getTaskStatus: async (taskId: string): Promise<TaskInfo> => {
  const resp = await axios.get(`/api/tasks/${taskId}/status`);
  return resp.data;
},

cancelTask: async (taskId: string): Promise<void> => {
  await axios.delete(`/api/tasks/${taskId}`);
},

// 表格
listTables: async (projectId: string): Promise<RawTable[]> => {
  const resp = await axios.get(`/api/projects/${projectId}/tables`);
  return resp.data;
},
```

### components/stages/file-uploader.tsx

```typescript
interface FileUploaderProps {
  projectId: string;
  onUploadComplete: (response: FileUploadResponse) => void;
  onError: (error: string) => void;
}
```

**功能要点：**
- 支持拖拽上传和点击选择文件
- 限制文件类型：`.xlsx`、`.docx`、`.pdf`
- 上传后调用 `api.uploadFile()`
- 返回 `FileUploadResponse`（含 task_id）
- 显示上传中的 loading 状态

### components/stages/import-stage.tsx

```typescript
interface ImportStageProps {
  projectId: string;
}
```

**功能要点：**
- 顶部：FileUploader（文件上传区）
- 中部：已上传文件列表（含解析状态）
- 每个文件显示：文件名、供应商名称（猜测值）、解析状态（进行中/完成/失败）
- 解析进行中时显示进度条，轮询 `api.getTaskStatus()` 获取进度
- 轮询间隔：1 秒
- 解析完成后自动刷新表格列表
- 解析失败时显示错误信息

**进度轮询逻辑：**
```typescript
// 上传完成后开始轮询
const pollTaskStatus = async (taskId: string) => {
  const poll = setInterval(async () => {
    const status = await api.getTaskStatus(taskId);
    // 更新进度 UI
    if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
      clearInterval(poll);
      // 刷新文件列表和表格列表
    }
  }, 1000);
};
```

### project-workbench.tsx 修改

在工作台页面中集成 ImportStage 组件：

```typescript
// 根据当前阶段渲染对应组件
// Phase 1 仅实现 ImportStage，其余阶段显示占位
{currentStage === 'import' && <ImportStage projectId={projectId} />}
```

## 测试与验收

### 门禁检查

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

### 手动验收

- 进入项目工作台 → 显示文件上传区域
- 拖拽 .xlsx 文件到上传区 → 显示上传中状态
- 上传完成后 → 显示解析进度条（进度从 0 到 1）
- 解析完成 → 文件列表中显示该文件（含猜测的供应商名称）
- 上传 .txt 文件 → 后端返回 400，前端显示错误提示
- 上传多个文件 → 各自独立显示解析进度
- 解析失败 → 显示错误信息

**断言清单：**
- `pnpm lint` → 退出码 0
- `pnpm tsc --noEmit` → 退出码 0
- types/file.ts 和 types/task.ts 中的类型定义与 openapi.json 中的 schema 一致
- FileUploader 组件限制接受 .xlsx/.docx/.pdf 文件
- ImportStage 正确轮询任务状态并更新进度
- API 调用封装在 api.ts 中，组件不直接使用 axios

## 提交

```bash
git add frontend/src/components/stages/import-stage.tsx \
       frontend/src/components/stages/file-uploader.tsx \
       frontend/src/types/file.ts frontend/src/types/task.ts \
       frontend/src/lib/api.ts frontend/src/app/project-workbench.tsx
git commit -m "Phase 1.7: 前端 ImportStage — 文件上传 + 解析进度轮询"
```
