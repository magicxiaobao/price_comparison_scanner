import axios from "axios";
import type { ProjectSummary, ProjectDetail, CreateProjectRequest } from "../types/project";
import type {
  CommodityGroup,
  GroupingGenerateResponse,
  GroupConfirmResponse,
  GroupSplitResponse,
  GroupMergeResponse,
  GroupMoveMemberResponse,
} from "../types/grouping";
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
import type {
  RequirementItem,
  RequirementCreate,
  RequirementUpdate,
  RequirementImportResult,
  ComplianceMatrix,
} from "../types/compliance";
import type { ComparisonResult } from "../types/comparison";
import type { ProblemGroup } from "../types/problem";

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

/** 配置 Tauri 模式的连接信息 */
function configureTauriConnection(port: number, token: string): void {
  client.defaults.baseURL = `http://127.0.0.1:${port}`;
  client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

/** 开发模式：从环境变量注入 token（如有） */
const devToken = import.meta.env.VITE_DEV_TOKEN;
if (devToken) {
  client.defaults.headers.common["Authorization"] = `Bearer ${devToken}`;
}

interface SidecarInfo {
  port: number;
  token: string;
  safeMode?: boolean;
}

/**
 * 统一 API 连接初始化。
 * - Tauri 模式：通过 invoke 从 Rust 端获取 sidecar 的 port 和 token
 * - 开发模式：保持现有逻辑（Vite proxy + VITE_DEV_TOKEN 环境变量）
 *
 * 必须在 React 渲染前调用。
 */
export async function initApiConnection(): Promise<void> {
  const { isTauri } = await import("@tauri-apps/api/core");
  if (isTauri()) {
    const { invoke } = await import("@tauri-apps/api/core");

    // 重试最多 30 次（每秒 1 次），等待异步 sidecar 启动完成
    let lastError = "";
    for (let i = 0; i < 30; i++) {
      try {
        const info = await invoke<SidecarInfo>("get_sidecar_info");
        configureTauriConnection(info.port, info.token);

        // Listen for sidecar restart events (port may change)
        const { listen } = await import("@tauri-apps/api/event");
        await listen<{ port: number }>("sidecar-restarted", (event) => {
          configureTauriConnection(event.payload.port, info.token);
          console.log(`[sidecar] restarted on port ${event.payload.port}`);
        });

        // Listen for safe mode (sidecar failed to recover)
        await listen("sidecar-safe-mode", () => {
          showSafeModeOverlay();
        });

        return; // 成功，退出
      } catch (err) {
        const errStr = String(err);
        if (errStr.includes("STARTING")) {
          // sidecar 还在启动中，继续等待
          await new Promise((r) => setTimeout(r, 1000));
          continue;
        }
        // 其他错误（STARTUP_FAILED 等），不再重试
        lastError = errStr.replace("STARTUP_FAILED:", "");
        break;
      }
    }
    throw new Error(lastError || "Sidecar 启动超时");
  }
}

/** Display a blocking overlay when sidecar enters safe mode */
function showSafeModeOverlay(): void {
  if (document.getElementById("sidecar-safe-mode-overlay")) return;

  const overlay = document.createElement("div");
  overlay.id = "sidecar-safe-mode-overlay";
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px)";
  overlay.innerHTML = `
    <div style="background:white;border-radius:12px;padding:32px 40px;max-width:420px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.2)">
      <div style="font-size:36px;margin-bottom:12px">&#9888;</div>
      <h2 style="margin:0 0 8px;font-size:18px;font-weight:600;color:#1a1a1a">后端服务异常</h2>
      <p style="margin:0 0 20px;font-size:14px;color:#666;line-height:1.6">
        后端服务多次启动失败，无法自动恢复。<br/>请关闭并重新启动应用。<br/>如问题持续，请联系技术支持。
      </p>
      <button onclick="location.reload()"
        style="padding:8px 24px;border:1px solid #d1d5db;border-radius:6px;background:#f9fafb;cursor:pointer;font-size:14px;color:#374151">
        尝试刷新
      </button>
    </div>
  `;
  document.body.appendChild(overlay);
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

// ---- Commodity Grouping API ----

export async function generateGrouping(projectId: string): Promise<GroupingGenerateResponse> {
  const resp = await client.post<GroupingGenerateResponse>(`/api/projects/${projectId}/grouping/generate`);
  return resp.data;
}

export async function listGroups(projectId: string): Promise<CommodityGroup[]> {
  const resp = await client.get<CommodityGroup[]>(`/api/projects/${projectId}/groups`);
  return resp.data;
}

export async function confirmGroup(groupId: string, projectId: string): Promise<GroupConfirmResponse> {
  const resp = await client.put<GroupConfirmResponse>(`/api/groups/${groupId}/confirm`, { projectId });
  return resp.data;
}

export async function splitGroup(groupId: string, projectId: string, newGroups: string[][]): Promise<GroupSplitResponse> {
  const resp = await client.put<GroupSplitResponse>(`/api/groups/${groupId}/split`, { projectId, newGroups });
  return resp.data;
}

export async function mergeGroups(projectId: string, groupIds: string[]): Promise<GroupMergeResponse> {
  const resp = await client.post<GroupMergeResponse>(`/api/projects/${projectId}/grouping/merge`, { groupIds });
  return resp.data;
}

export async function markNotComparable(groupId: string, projectId: string): Promise<{ id: string; status: string }> {
  const resp = await client.put<{ id: string; status: string }>(`/api/groups/${groupId}/not-comparable`, { projectId });
  return resp.data;
}

export async function moveMember(groupId: string, projectId: string, targetGroupId: string, rowId: string): Promise<GroupMoveMemberResponse> {
  const resp = await client.put<GroupMoveMemberResponse>(`/api/groups/${groupId}/move-member`, { projectId, targetGroupId, rowId });
  return resp.data;
}

// ---- 需求标准 API ----

export async function createRequirement(
  projectId: string,
  data: RequirementCreate,
): Promise<RequirementItem> {
  const resp = await client.post<RequirementItem>(
    `/api/projects/${projectId}/requirements`,
    data,
  );
  return resp.data;
}

export async function listRequirements(
  projectId: string,
): Promise<RequirementItem[]> {
  const resp = await client.get<RequirementItem[]>(
    `/api/projects/${projectId}/requirements`,
  );
  return resp.data;
}

export async function updateRequirement(
  reqId: string,
  data: RequirementUpdate,
): Promise<RequirementItem> {
  const resp = await client.put<RequirementItem>(
    `/api/requirements/${reqId}`,
    data,
  );
  return resp.data;
}

export async function deleteRequirement(
  reqId: string,
  projectId: string,
): Promise<void> {
  await client.delete(`/api/requirements/${reqId}`, {
    params: { project_id: projectId },
  });
}

export async function importRequirements(
  projectId: string,
  file: File,
): Promise<RequirementImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await client.post<RequirementImportResult>(
    `/api/projects/${projectId}/requirements/import`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return resp.data;
}

export async function exportRequirements(projectId: string): Promise<Blob> {
  const resp = await client.get(
    `/api/projects/${projectId}/requirements/export`,
    { responseType: "blob" },
  );
  return resp.data as Blob;
}

// ---- 符合性审查 API ----

export async function evaluateCompliance(
  projectId: string,
): Promise<{ taskId: string }> {
  const resp = await client.post<{ taskId: string }>(
    `/api/projects/${projectId}/compliance/evaluate`,
  );
  return resp.data;
}

export async function getComplianceMatrix(
  projectId: string,
): Promise<ComplianceMatrix> {
  const resp = await client.get<ComplianceMatrix>(
    `/api/projects/${projectId}/compliance/matrix`,
  );
  return resp.data;
}

export async function confirmMatch(
  matchId: string,
  projectId: string,
  status: string,
): Promise<void> {
  await client.put(`/api/compliance/${matchId}/confirm`, {
    projectId,
    status,
  });
}

export async function acceptMatch(
  matchId: string,
  projectId: string,
  isAcceptable: boolean,
): Promise<void> {
  await client.put(`/api/compliance/${matchId}/accept`, {
    projectId,
    isAcceptable,
  });
}

// ---- 比价 API ----

export async function generateComparison(
  projectId: string,
): Promise<{ taskId: string }> {
  const resp = await client.post<{ taskId: string }>(
    `/api/projects/${projectId}/comparison/generate`,
  );
  return resp.data;
}

export async function getComparison(
  projectId: string,
): Promise<ComparisonResult[]> {
  const resp = await client.get<ComparisonResult[]>(
    `/api/projects/${projectId}/comparison`,
  );
  return resp.data;
}

// ---- 导出 API ----

export async function exportReport(
  projectId: string,
): Promise<{ taskId: string }> {
  const resp = await client.post<{ taskId: string }>(
    `/api/projects/${projectId}/export`,
  );
  return resp.data;
}

// ---- 问题清单 API ----

export async function getProblems(
  projectId: string,
): Promise<ProblemGroup[]> {
  const resp = await client.get<ProblemGroup[]>(
    `/api/projects/${projectId}/problems`,
  );
  return resp.data;
}

export default client;
