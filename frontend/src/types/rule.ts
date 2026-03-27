/** 匹配模式 */
export type MatchMode = "exact" | "fuzzy" | "regex";

/** 规则类型 */
export type RuleType = "column_mapping" | "value_normalization";

/** 规则来源 */
export type RuleSource = "template" | "global" | "project";

/** 列名映射规则 */
export interface ColumnMappingRule {
  id: string;
  enabled: boolean;
  type: "column_mapping";
  sourceKeywords: string[];
  targetField: string;
  matchMode: MatchMode;
  priority: number;
  createdAt: string;
}

/** 值标准化辅助规则 */
export interface ValueNormalizationRule {
  id: string;
  type: "value_normalization";
  field: string;
  patterns: string[];
  replaceWith: string;
  createdAt: string;
}

/** 完整规则集 */
export interface RuleSet {
  version: string;
  lastUpdated: string;
  columnMappingRules: ColumnMappingRule[];
  valueNormalizationRules: ValueNormalizationRule[];
}

/** 规则测试结果 */
export interface RuleTestResult {
  matched: boolean;
  targetField: string | null;
  matchedRule: Record<string, unknown> | null;
  conflicts: Record<string, unknown>[];
  resolution: string | null;
}

/** 规则导入汇总 */
export interface RuleImportSummary {
  total: number;
  added: number;
  conflicts: number;
  skipped: number;
}

/** 新增/编辑规则请求 */
export interface RuleCreateUpdate {
  type: RuleType;
  sourceKeywords?: string[];
  targetField?: string;
  matchMode?: MatchMode;
  priority?: number;
  field?: string;
  patterns?: string[];
  replaceWith?: string;
}

/** 模板信息 */
export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  ruleCount: number;
}
