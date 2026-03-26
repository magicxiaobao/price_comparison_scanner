# Task 1.9: 前端 ProjectStore 扩展（阶段状态）

## 输入条件

- Task 1.7 完成（ImportStage 文件上传就绪）
- Task 1.8 完成（供应商确认 + 表格选择 UI 就绪）
- Phase 0 前端 ProjectStore 最小接口就绪

## 输出物

- 修改: `frontend/src/stores/project-store.ts`（扩展阶段状态管理和文件/表格状态）
- 修改: `frontend/src/app/project-workbench.tsx`（使用 ProjectStore 管理 ImportStage 数据）

## 禁止修改

- 不修改 `backend/`
- 不修改 `frontend/src/app/home-page.tsx`
- 不修改 `frontend/src/components/stages/file-uploader.tsx`
- 不修改 `frontend/src/types/`

## 实现规格

### stores/project-store.ts 扩展

在 Phase 0 的 ProjectStore 基础上扩展以下状态和方法：

```typescript
interface ProjectStore {
  // === Phase 0 已有 ===
  currentProject: Project | null;
  stageStatuses: StageStatuses;
  isLoading: boolean;
  loadProject: (id: string) => Promise<void>;
  clearProject: () => void;

  // === Phase 1 新增 ===

  // 文件相关状态
  files: SupplierFile[];
  tables: RawTable[];
  activeTasks: Map<string, TaskInfo>;   // task_id → 最新状态

  // 文件相关方法
  loadFiles: (projectId: string) => Promise<void>;
  loadTables: (projectId: string) => Promise<void>;
  addUploadTask: (taskId: string, fileId: string) => void;
  updateTaskStatus: (taskId: string, status: TaskInfo) => void;
  removeTask: (taskId: string) => void;

  // 导入阶段状态计算
  importProgress: () => {
    totalFiles: number;
    confirmedFiles: number;
    selectedTables: number;
    totalTables: number;
    allConfirmed: boolean;            // 所有文件都已确认供应商
  };
}
```

**设计要点：**
- `files` 和 `tables` 从后端 API 加载后缓存在 Store 中
- `activeTasks` 用于跟踪正在进行的解析任务
- `importProgress()` 是计算属性，用于 ImportStage 底部汇总显示
- `loadFiles` 和 `loadTables` 分别调用 `api.listFiles()` 和 `api.listTables()`
- 文件上传完成后调用 `addUploadTask()` 注册任务，轮询更新后调用 `updateTaskStatus()`

### project-workbench.tsx 修改

工作台页面使用 ProjectStore 管理数据流：

```typescript
// 进入工作台时
useEffect(() => {
  if (projectId) {
    loadProject(projectId);
    loadFiles(projectId);
    loadTables(projectId);
  }
}, [projectId]);

// ImportStage 从 Store 读取数据
<ImportStage
  projectId={projectId}
  files={files}
  tables={tables}
  onFileUploaded={handleFileUploaded}
/>
```

## 测试与验收

### 门禁检查

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

### 手动验收

- 进入项目工作台 → ProjectStore 自动加载文件和表格数据
- 上传文件后 → Store 中 files 列表更新
- 解析完成后 → Store 中 tables 列表更新
- 确认供应商后 → Store 中对应 file 的 supplier_confirmed 更新
- `importProgress()` 返回正确的统计信息
- 切换表格选择后 → Store 中对应 table 的 selected 更新

**断言清单：**
- `pnpm lint` → 退出码 0
- `pnpm tsc --noEmit` → 退出码 0
- ProjectStore 的 `files` 和 `tables` 初始值为空数组
- `loadFiles()` 调用后 `files` 包含后端返回的数据
- `importProgress().allConfirmed` 在所有文件确认后为 true
- `activeTasks` 正确跟踪进行中的解析任务

## 提交

```bash
git add frontend/src/stores/project-store.ts \
       frontend/src/app/project-workbench.tsx
git commit -m "Phase 1.9: ProjectStore 扩展 — 文件/表格状态 + 阶段进度计算"
```
