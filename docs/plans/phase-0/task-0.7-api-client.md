# Task 0.7: 前端 API Client 封装

## 输入条件

- Task 0.6 完成（前端骨架存在，axios 已安装）

## 输出物

- 创建: `frontend/src/lib/api.ts`
- 创建: `frontend/src/types/project.ts`
- 创建: `frontend/src/types/api.ts`
- 创建: `frontend/src/stores/project-store.ts`（最小版骨架）

## 禁止修改

- 不修改 `backend/`
- 不修改 `src/App.tsx`（路由结构已稳定）
- 不修改 `vite.config.ts`（proxy 已配置）

## 实现规格

### types/api.ts

```typescript
/** API 错误响应 */
export interface ApiError {
  detail: string;
}
```

### types/project.ts

```typescript
/** 阶段状态 */
export interface StageStatuses {
  import_status: "pending" | "completed" | "dirty";
  normalize_status: "pending" | "completed" | "dirty";
  grouping_status: "pending" | "completed" | "dirty";
  compliance_status: "skipped" | "pending" | "completed" | "dirty";
  comparison_status: "pending" | "completed" | "dirty";
}

/** 项目列表项 */
export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  supplier_count: number;
  current_stage: string;
}

/** 项目详情 */
export interface ProjectDetail {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  stage_statuses: StageStatuses;
}

/** 创建项目请求 */
export interface CreateProjectRequest {
  name: string;
}
```

### lib/api.ts

```typescript
import axios from "axios";
import type { ProjectSummary, ProjectDetail, CreateProjectRequest } from "../types/project";

/**
 * API 客户端。
 *
 * 开发模式：Vite proxy 将 /api 转发到后端，无需手动设置 baseURL。
 * Tauri 模式：通过 Tauri invoke 获取端口和 token，设置 baseURL 和 Authorization。
 */
const client = axios.create({
  baseURL: "",
  headers: { "Content-Type": "application/json" },
});

/** 配置 Tauri 模式的连接信息（Phase 5 Tauri 集成时调用） */
export function configureTauriConnection(port: number, token: string): void {
  client.defaults.baseURL = `http://127.0.0.1:${port}`;
  client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

/** 开发模式：从环境变量注入 token（如有） */
const devToken = import.meta.env.VITE_DEV_TOKEN;
if (devToken) {
  client.defaults.headers.common["Authorization"] = `Bearer ${devToken}`;
}

// ---- 项目 API ----

export async function createProject(req: CreateProjectRequest): Promise<ProjectDetail> {
  const resp = await client.post<ProjectDetail>("/api/projects", req);
  return resp.data;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const resp = await client.get<ProjectSummary[]>("/api/projects");
  return resp.data;
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const resp = await client.get<ProjectDetail>(`/api/projects/${id}`);
  return resp.data;
}

export async function deleteProject(id: string): Promise<void> {
  await client.delete(`/api/projects/${id}`);
}

export default client;
```

**设计要点：**
- 开发模式下 `baseURL` 为空，依赖 Vite proxy（`/api → http://127.0.0.1:17396`）
- Tauri 模式下通过 `configureTauriConnection()` 注入端口和 token（Phase 5 调用）
- 开发模式下可选通过 `VITE_DEV_TOKEN` 环境变量注入 token
- 每个 API 方法返回类型化的数据，不返回 AxiosResponse
- 后续 Phase 在此文件追加新的 API 方法

### stores/project-store.ts（最小版）

```typescript
import { create } from "zustand";
import type { ProjectSummary, ProjectDetail, StageStatuses } from "../types/project";
import * as api from "../lib/api";

interface ProjectStore {
  /** 最近项目列表 */
  projects: ProjectSummary[];
  /** 当前打开的项目 */
  currentProject: ProjectDetail | null;
  /** 加载状态 */
  isLoading: boolean;

  /** 加载项目列表 */
  loadProjects: () => Promise<void>;
  /** 加载项目详情 */
  loadProject: (id: string) => Promise<void>;
  /** 创建项目 */
  createProject: (name: string) => Promise<ProjectDetail>;
  /** 删除项目 */
  deleteProject: (id: string) => Promise<void>;
  /** 清除当前项目 */
  clearProject: () => void;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  currentProject: null,
  isLoading: false,

  loadProjects: async () => {
    set({ isLoading: true });
    const projects = await api.listProjects();
    set({ projects, isLoading: false });
  },

  loadProject: async (id: string) => {
    set({ isLoading: true });
    const project = await api.getProject(id);
    set({ currentProject: project, isLoading: false });
  },

  createProject: async (name: string) => {
    const project = await api.createProject({ name });
    await get().loadProjects();
    return project;
  },

  deleteProject: async (id: string) => {
    await api.deleteProject(id);
    await get().loadProjects();
    if (get().currentProject?.id === id) {
      set({ currentProject: null });
    }
  },

  clearProject: () => set({ currentProject: null }),
}));
```

## 测试与验收

```bash
cd frontend

# 1. TypeScript 类型检查
pnpm tsc --noEmit                     # exit 0

# 2. ESLint 检查
pnpm lint                             # exit 0

# 3. 文件存在且可 import
test -f src/lib/api.ts
test -f src/types/project.ts
test -f src/types/api.ts
test -f src/stores/project-store.ts
```

**断言清单：**
- `pnpm tsc --noEmit` → 退出码 0（类型定义与后端 API 匹配）
- `pnpm lint` → 退出码 0
- `api.ts` 导出 `createProject`, `listProjects`, `getProject`, `deleteProject`
- `project-store.ts` 导出 `useProjectStore`
- 类型定义与 `openapi.json` 中的 schema 一致

## 提交

```bash
git add frontend/src/lib/ frontend/src/types/ frontend/src/stores/
git commit -m "Phase 0.7: 前端 API Client 封装 + TypeScript 类型定义 + ProjectStore 骨架"
```
