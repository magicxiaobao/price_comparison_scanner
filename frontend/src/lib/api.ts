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
