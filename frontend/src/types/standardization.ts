/** 来源位置项（对应 SourceLocationItem） */
export interface SourceLocationItem {
  type: string;
  sheet?: string | null;
  cell?: string | null;
  table_index?: number | null;
  row?: number | null;
  col?: number | null;
  page?: number | null;
  extraction_mode?: string | null;
  ocr_confidence?: number | null;
}

export type SourceLocation = Record<string, SourceLocationItem>;

/** 规则命中快照（对应 HitRuleSnapshot） */
export interface HitRuleSnapshot {
  rule_id: string;
  rule_name: string;
  match_content: string;
  match_mode: string;
}

/** 标准化行（对应 StandardizedRowResponse） */
export interface StandardizedRow {
  id: string;
  rawTableId: string;
  supplierFileId: string;
  rowIndex: number;
  product_name: string | null;
  spec_model: string | null;
  unit: string | null;
  quantity: number | null;
  unit_price: number | null;
  total_price: number | null;
  tax_rate: string | null;
  delivery_period: string | null;
  remark: string | null;
  sourceLocation: SourceLocation;
  columnMapping: Record<string, string> | null;
  hitRuleSnapshots: HitRuleSnapshot[] | null;
  confidence: number;
  isManuallyModified: boolean;
  needsReview: boolean;
  taxBasis: string | null;
}

/** 列名映射信息（对应 column-mapping-info API 响应） */
export interface ColumnMappingInfo {
  originalColumn: string;
  targetField: string | null;
  matchedRule: string | null;
  matchMode: string | null;
  status: "confirmed" | "pending" | "unmapped" | "conflict";
}

/** 手工修正响应（对应 FieldModifyResponse） */
export interface FieldModifyResponse {
  success: boolean;
  auditLog: {
    field: string;
    beforeValue: string;
    afterValue: string;
    timestamp: string;
  };
  dirtyStages?: string[];
}

/** 标准字段的键名（9 个标准字段） */
export type StandardFieldKey =
  | "product_name"
  | "spec_model"
  | "unit"
  | "quantity"
  | "unit_price"
  | "total_price"
  | "tax_rate"
  | "delivery_period"
  | "remark";

/** 标准字段显示名 */
export const STANDARD_FIELD_LABELS: Record<StandardFieldKey, string> = {
  product_name: "品名",
  spec_model: "规格型号",
  unit: "单位",
  quantity: "数量",
  unit_price: "单价",
  total_price: "总价",
  tax_rate: "税率",
  delivery_period: "交货期",
  remark: "备注",
};

/** 必填字段 */
export const REQUIRED_FIELDS: StandardFieldKey[] = [
  "product_name",
  "unit_price",
  "quantity",
];
