/** 归组成员摘要 */
export interface GroupMemberSummary {
  standardizedRowId: string;
  supplierName: string;
  productName: string;
  specModel: string;
  unit: string;
  unitPrice: number | null;
  quantity: number | null;
  confidence: number;
}

/** 归组响应 (CommodityGroupResponse) */
export interface CommodityGroup {
  id: string;
  projectId: string;
  groupName: string;
  normalizedKey: string;
  confidenceLevel: "high" | "medium" | "low";
  matchScore: number;
  matchReason: string;
  status: "candidate" | "confirmed" | "split" | "not_comparable";
  confirmedAt: string | null;
  members: GroupMemberSummary[];
  memberCount: number;
}

/** 生成归组响应 */
export interface GroupingGenerateResponse {
  taskId: string;
}

/** 确认归组响应 */
export interface GroupConfirmResponse {
  id: string;
  status: string;
  confirmedAt: string;
}

/** 拆分请求 */
export interface GroupSplitRequest {
  newGroups: string[][];
}

/** 拆分响应 */
export interface GroupSplitResponse {
  originalGroupId: string;
  newGroups: CommodityGroup[];
}

/** 合并请求 */
export interface GroupMergeRequest {
  groupIds: string[];
}

/** 合并响应 */
export interface GroupMergeResponse {
  mergedGroup: CommodityGroup;
  removedGroupIds: string[];
}

/** 移动成员响应 */
export interface GroupMoveMemberResponse {
  sourceGroup: CommodityGroup;
  targetGroup: CommodityGroup;
  movedRowId: string;
}
