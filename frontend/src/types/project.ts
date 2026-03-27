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
