# Task 3.5: 前端 GroupingStage — 候选归组列表（置信度分层）

## 输入条件

- Task 3.3 完成（归组 API 可用）
- Task 3.8 完成或进行中（openapi.json 已更新，可通过 MCP 查询）
- 前端基础设施就绪（React + Tailwind + Zustand + API Client）

> **MCP 强制规则**：实现前必须通过 openapi-contract MCP 工具查询归组相关 API 定义，不可凭假设编码。

## 输出物

- 创建: `frontend/src/types/grouping.ts`
- 创建: `frontend/src/components/stages/grouping-stage.tsx`
- 创建: `frontend/src/components/stages/group-candidate-list.tsx`
- 修改: `frontend/src/app/project-workbench.tsx`（在阶段导航中注册 GroupingStage）
- 创建: `frontend/src/stores/grouping-store.ts`（独立归组状态管理）

## 禁止修改

- 不修改 `backend/`
- 不修改已有的前端组件签名（ImportStage, StandardizeStage 等）
- 不修改 `frontend/src/lib/api.ts` 的已有接口（可追加新方法）

## 实现规格

### types/grouping.ts

```typescript
/** 归组成员摘要 */
export interface GroupMemberSummary {
  standardized_row_id: string;
  supplier_name: string;
  product_name: string;
  spec: string;
  unit: string;
  unit_price: number | null;
  quantity: number | null;
  confidence: number;
}

/** 归组响应 */
export interface CommodityGroup {
  id: string;
  project_id: string;
  group_name: string;
  normalized_key: string;
  confidence_level: "high" | "medium" | "low";
  match_score: number;
  match_reason: string;
  status: "candidate" | "confirmed" | "split" | "not_comparable";
  confirmed_at: string | null;
  members: GroupMemberSummary[];
  member_count: number;
}

/** 生成归组响应 */
export interface GroupingGenerateResponse {
  task_id: string;
}

/** 确认归组响应 */
export interface GroupConfirmResponse {
  id: string;
  status: string;
  confirmed_at: string;
}

/** 拆分请求 */
export interface GroupSplitRequest {
  new_groups: string[][];
}

/** 拆分响应 */
export interface GroupSplitResponse {
  original_group_id: string;
  new_groups: CommodityGroup[];
}

/** 合并请求 */
export interface GroupMergeRequest {
  group_ids: string[];
}

/** 合并响应 */
export interface GroupMergeResponse {
  merged_group: CommodityGroup;
  removed_group_ids: string[];
}
```

### lib/api.ts（追加方法）

```typescript
// ---- 归组 API ----

async generateGrouping(projectId: string): Promise<GroupingGenerateResponse> {
  const resp = await this.client.post(`/api/projects/${projectId}/grouping/generate`);
  return resp.data;
}

async listGroups(projectId: string): Promise<CommodityGroup[]> {
  const resp = await this.client.get(`/api/projects/${projectId}/groups`);
  return resp.data;
}

async confirmGroup(groupId: string): Promise<GroupConfirmResponse> {
  const resp = await this.client.put(`/api/groups/${groupId}/confirm`);
  return resp.data;
}

async splitGroup(groupId: string, newGroups: string[][]): Promise<GroupSplitResponse> {
  const resp = await this.client.put(`/api/groups/${groupId}/split`, { new_groups: newGroups });
  return resp.data;
}

async mergeGroups(projectId: string, groupIds: string[]): Promise<GroupMergeResponse> {
  const resp = await this.client.post(`/api/projects/${projectId}/grouping/merge`, { group_ids: groupIds });
  return resp.data;
}

async markNotComparable(groupId: string): Promise<{ id: string; status: string }> {
  const resp = await this.client.put(`/api/groups/${groupId}/not-comparable`);
  return resp.data;
}
```

### components/stages/grouping-stage.tsx

```tsx
/**
 * GroupingStage — 商品归组阶段主容器
 *
 * 职责：
 * 1. 触发生成归组候选（调 API + 轮询任务状态）
 * 2. 展示 GroupCandidateList
 * 3. 管理归组操作状态
 */

interface GroupingStageProps {
  projectId: string;
}

// 主要状态：
// - groups: CommodityGroup[] — 当前归组列表
// - isGenerating: boolean — 是否正在生成
// - selectedGroupIds: string[] — 选中的归组（用于合并）
//
// 主要交互：
// - "生成归组" 按钮 → POST /api/projects/{id}/grouping/generate → 轮询任务 → 刷新列表
// - "重新生成" 按钮 → 确认后重新生成（会清除已有归组）
// - 将 groups 按 confidence_level 分为三组传给 GroupCandidateList
```

### components/stages/group-candidate-list.tsx

```tsx
/**
 * GroupCandidateList — 候选归组列表（按置信度分层展示）
 *
 * 展示规则：
 * 1. 分三个区域：高置信（绿色标识）/ 中置信（黄色标识）/ 低置信（灰色标识）
 * 2. 每个归组显示：
 *    - 归组名称 (group_name)
 *    - 置信度标签 + 分数 (match_score)
 *    - 归组理由 (match_reason)
 *    - 状态标签 (status: candidate/confirmed/not_comparable)
 *    - 成员数量 (member_count)
 *    - 可展开的成员列表
 * 3. 每个成员行显示：
 *    - 供应商名称
 *    - 商品名称
 *    - 规格型号
 *    - 单位
 *    - 单价
 *    - 数量
 *
 * 操作按钮（每个归组卡片）：
 * - 确认 (confirm) — 仅 candidate 状态可用
 * - 拆分 (split) — 成员 >= 2 时可用
 * - 标记不可比 (not_comparable)
 * - 选中复选框（用于批量合并）
 *
 * 全局操作：
 * - 合并选中的归组（选中 >= 2 个时可用）
 */

interface GroupCandidateListProps {
  groups: CommodityGroup[];
  onConfirm: (groupId: string) => void;
  onSplit: (groupId: string, newGroups: string[][]) => void;
  onMerge: (groupIds: string[]) => void;
  onMarkNotComparable: (groupId: string) => void;
}

// 置信度分层颜色：
// high: bg-green-50 border-green-200 text-green-700
// medium: bg-yellow-50 border-yellow-200 text-yellow-700
// low: bg-gray-50 border-gray-200 text-gray-500
//
// 状态标签颜色：
// candidate: bg-blue-100 text-blue-700
// confirmed: bg-green-100 text-green-700
// not_comparable: bg-red-100 text-red-700
```

### 关键交互流程

1. **首次进入归组阶段**：
   - 检查 `grouping_status`，如果是 `pending` 显示 "生成归组" 按钮
   - 如果是 `completed` 或 `dirty`，自动加载已有归组列表
   - 如果是 `dirty`，顶部显示"归组数据已失效，建议重新生成"提示

2. **生成归组**：
   - 点击 → POST generate → 获取 task_id → 轮询 GET /api/tasks/{task_id}/status
   - 生成中显示进度
   - 完成后自动加载归组列表

3. **展示归组列表**：
   - 按置信度分三个区域展示
   - 每个归组可展开/折叠成员列表
   - 独立项（member_count == 1）灰色展示在低置信区域

## 测试与验收

### 门禁命令

```bash
cd frontend
pnpm lint                    # exit 0
pnpm tsc --noEmit            # exit 0
```

### 手动验收

- [ ] 归组阶段在工作台中正确显示（第三步位置）
- [ ] 点击"生成归组"按钮 → 异步生成 → 显示进度 → 完成后展示列表
- [ ] 高置信归组显示绿色标识
- [ ] 中置信归组显示黄色标识
- [ ] 低置信/独立项显示灰色标识
- [ ] 每个归组可展开查看成员详情（供应商、商品名、规格、单位、单价）
- [ ] 归组理由 (match_reason) 正确显示
- [ ] 状态标签正确显示
- [ ] TypeScript 类型与 openapi.json 契约一致

**断言清单：**

| 断言 | 预期 |
|------|------|
| `pnpm lint` | exit 0 |
| `pnpm tsc --noEmit` | exit 0 |
| `grouping.ts` 类型与 openapi.json 一致 | 字段名和类型匹配 |
| API 调用方法在 `api.ts` 中已定义 | 6 个方法（generate, list, confirm, split, merge, markNotComparable） |
| 三种置信度分层展示 | 颜色区分正确 |

## 提交

```bash
git add frontend/src/types/grouping.ts \
       frontend/src/components/stages/grouping-stage.tsx \
       frontend/src/components/stages/group-candidate-list.tsx \
       frontend/src/lib/api.ts \
       frontend/src/app/project-workbench.tsx \
       frontend/src/stores/grouping-store.ts
git commit -m "Phase 3.5: 前端 GroupingStage — 候选归组列表 + 置信度分层展示 + 归组类型定义"
```
