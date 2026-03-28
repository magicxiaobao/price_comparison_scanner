/** 需求项（对应后端 RequirementResponse） */
export interface RequirementItem {
  id: string;
  projectId: string;
  code: string | null;
  category: "功能要求" | "技术规格" | "商务条款" | "服务要求" | "交付要求";
  title: string;
  description: string | null;
  isMandatory: boolean;
  matchType: "keyword" | "numeric" | "manual";
  expectedValue: string | null;
  operator: "gte" | "lte" | "eq" | "range" | null;
  sortOrder: number;
  createdAt: string;
}

/** 创建需求项请求（对应后端 RequirementCreate） */
export interface RequirementCreate {
  code?: string | null;
  category: string;
  title: string;
  description?: string | null;
  isMandatory?: boolean;
  matchType: string;
  expectedValue?: string | null;
  operator?: string | null;
}

/** 更新需求项请求（对应后端 RequirementUpdate） */
export interface RequirementUpdate {
  projectId: string;
  code?: string | null;
  category?: string | null;
  title?: string | null;
  description?: string | null;
  isMandatory?: boolean | null;
  matchType?: string | null;
  expectedValue?: string | null;
  operator?: string | null;
}

/** 符合性矩阵单元格（对应后端 ComplianceMatrixCell） */
export interface ComplianceMatrixCell {
  matchId: string;
  status: "match" | "partial" | "no_match" | "unclear";
  isAcceptable: boolean;
  needsReview: boolean;
  evidenceText: string | null;
}

/** 符合性矩阵行（对应后端 ComplianceMatrixRow） */
export interface ComplianceMatrixRow {
  requirement: RequirementItem;
  suppliers: Record<string, ComplianceMatrixCell>;
}

/** 符合性矩阵完整响应（对应后端 ComplianceMatrixResponse） */
export interface ComplianceMatrix {
  supplierNames: Record<string, string>;
  rows: ComplianceMatrixRow[];
}

/** 需求导入结果（对应后端 RequirementImportResult） */
export interface RequirementImportResult {
  total: number;
  imported: number;
  skipped: number;
  errors: string[];
}

/** 需求项分类枚举 */
export const CATEGORY_OPTIONS = [
  "功能要求",
  "技术规格",
  "商务条款",
  "服务要求",
  "交付要求",
] as const;

/** 匹配类型枚举 */
export const MATCH_TYPE_OPTIONS = [
  { value: "keyword", label: "关键词" },
  { value: "numeric", label: "数值" },
  { value: "manual", label: "人工" },
] as const;

/** 操作符枚举 */
export const OPERATOR_OPTIONS = [
  { value: "gte", label: ">=" },
  { value: "lte", label: "<=" },
  { value: "eq", label: "=" },
  { value: "range", label: "区间" },
] as const;

/** 状态颜色映射 */
export const STATUS_STYLES: Record<
  ComplianceMatrixCell["status"],
  { bg: string; text: string; border: string; label: string }
> = {
  match: { bg: "bg-green-100", text: "text-green-800", border: "border-green-300", label: "符合" },
  partial: { bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-300", label: "部分符合" },
  no_match: { bg: "bg-red-100", text: "text-red-800", border: "border-red-300", label: "不符合" },
  unclear: { bg: "bg-gray-100", text: "text-gray-500", border: "border-gray-300", label: "待定" },
};
