import axios from "axios";
import type { ProjectSummary, ProjectDetail, CreateProjectRequest } from "../types/project";
import type { SupplierFile, FileUploadResponse, RawTable } from "../types/file";
import type { TaskInfo } from "../types/task";

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

// ---- 文件导入 API ----

export async function uploadFile(projectId: string, file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await client.post<FileUploadResponse>(
    `/api/projects/${projectId}/files`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return resp.data;
}

export async function listFiles(projectId: string): Promise<SupplierFile[]> {
  const resp = await client.get<SupplierFile[]>(`/api/projects/${projectId}/files`);
  return resp.data;
}

// ---- 异步任务 API ----

export async function getTaskStatus(taskId: string): Promise<TaskInfo> {
  const resp = await client.get<TaskInfo>(`/api/tasks/${taskId}/status`);
  return resp.data;
}

export async function cancelTask(taskId: string): Promise<void> {
  await client.delete(`/api/tasks/${taskId}`);
}

// ---- 表格 API ----

export async function listTables(projectId: string): Promise<RawTable[]> {
  const resp = await client.get<RawTable[]>(`/api/projects/${projectId}/tables`);
  return resp.data;
}

export default client;
