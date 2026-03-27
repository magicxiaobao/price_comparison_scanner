import axios from "axios";
import type { ProjectSummary, ProjectDetail, CreateProjectRequest } from "../types/project";
import type { SupplierFile, FileUploadResponse, RawTable } from "../types/file";
import type { TaskInfo } from "../types/task";
import type {
  RuleSet,
  RuleCreateUpdate,
  TemplateInfo,
  RuleTestResult,
  RuleImportSummary,
} from "../types/rule";
import type {
  StandardizedRow,
  ColumnMappingInfo,
  FieldModifyResponse,
} from "../types/standardization";

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

// ---- 供应商确认 API ----

export async function confirmSupplier(
  fileId: string,
  supplierName: string,
  projectId: string,
): Promise<SupplierFile> {
  const resp = await client.put<SupplierFile>(`/api/files/${fileId}/confirm-supplier`, {
    supplier_name: supplierName,
    project_id: projectId,
  });
  return resp.data;
}

// ---- 表格 API ----

export async function listTables(projectId: string): Promise<RawTable[]> {
  const resp = await client.get<RawTable[]>(`/api/projects/${projectId}/tables`);
  return resp.data;
}

export async function toggleTableSelection(
  tableId: string,
  projectId: string,
): Promise<{ table_id: string; selected: boolean }> {
  const resp = await client.put<{ table_id: string; selected: boolean }>(
    `/api/tables/${tableId}/toggle-selection`,
    { project_id: projectId },
  );
  return resp.data;
}

// ---- 规则管理 API ----

export async function getRules(): Promise<RuleSet> {
  const resp = await client.get<RuleSet>("/api/rules");
  return resp.data;
}

export async function getTemplates(): Promise<TemplateInfo[]> {
  const resp = await client.get<TemplateInfo[]>("/api/rules/templates");
  return resp.data;
}

export async function upsertRule(rule: RuleCreateUpdate): Promise<RuleSet> {
  const resp = await client.put<RuleSet>("/api/rules", rule);
  return resp.data;
}

export async function deleteRule(ruleId: string): Promise<void> {
  await client.delete(`/api/rules/${ruleId}`);
}

export async function toggleRule(ruleId: string): Promise<{ enabled: boolean }> {
  const resp = await client.put<{ enabled: boolean }>(`/api/rules/${ruleId}/toggle`);
  return resp.data;
}

export async function loadTemplate(templateId: string): Promise<RuleSet> {
  const resp = await client.post<RuleSet>("/api/rules/load-template", { templateId });
  return resp.data;
}

export async function resetDefault(): Promise<RuleSet> {
  const resp = await client.post<RuleSet>("/api/rules/reset-default");
  return resp.data;
}

export async function importRules(file: File, strategy?: string): Promise<RuleImportSummary> {
  const formData = new FormData();
  formData.append("file", file);
  if (strategy) formData.append("strategy", strategy);
  const resp = await client.post<RuleImportSummary>("/api/rules/import", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return resp.data;
}

export async function exportRules(): Promise<Blob> {
  const resp = await client.get("/api/rules/export", { responseType: "blob" });
  return resp.data as Blob;
}

export async function testRule(columnName: string, projectId?: string): Promise<RuleTestResult> {
  const resp = await client.post<RuleTestResult>("/api/rules/test", {
    columnName,
    projectId: projectId ?? null,
  });
  return resp.data;
}

// ---- 标准化 API ----

export async function runStandardization(
  projectId: string,
  force?: boolean,
): Promise<{ taskId: string }> {
  const resp = await client.post<{ taskId: string }>(
    `/api/projects/${projectId}/standardize`,
    force ? { force } : null,
  );
  return resp.data;
}

export async function getStandardizedRows(
  projectId: string,
): Promise<StandardizedRow[]> {
  const resp = await client.get<StandardizedRow[]>(
    `/api/projects/${projectId}/standardized-rows`,
  );
  return resp.data;
}

export async function modifyStandardizedRow(
  rowId: string,
  field: string,
  newValue: string | number | null,
): Promise<FieldModifyResponse> {
  const resp = await client.put<FieldModifyResponse>(
    `/api/standardized-rows/${rowId}`,
    { field, newValue },
  );
  return resp.data;
}

export async function getColumnMappingInfo(
  projectId: string,
): Promise<ColumnMappingInfo[]> {
  const resp = await client.get<ColumnMappingInfo[]>(
    `/api/projects/${projectId}/column-mapping-info`,
  );
  return resp.data;
}

export default client;
