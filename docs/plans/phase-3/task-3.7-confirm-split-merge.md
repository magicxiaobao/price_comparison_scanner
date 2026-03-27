# Task 3.7: 前端 GroupingStage — 确认/拆分/合并/标记不可比

## 输入条件

- Task 3.5 完成（GroupCandidateList 基础 UI 就绪）
- 归组 API 可用（Task 3.3）

> **MCP 强制规则**：实现前必须通过 openapi-contract MCP 工具查询确认/拆分/合并/标记不可比的 API 定义（请求体和响应结构），不可凭假设编码。

## 输出物

- 修改: `frontend/src/components/stages/group-candidate-list.tsx`（添加操作按钮和交互逻辑）
- 创建: `frontend/src/components/stages/group-split-dialog.tsx`（拆分对话框）
- 修改: `frontend/src/components/stages/grouping-stage.tsx`（添加合并操作逻辑）

## 禁止修改

- 不修改 `backend/`
- 不修改 `frontend/src/types/grouping.ts`（已稳定）
- 不修改 `frontend/src/lib/api.ts`（已稳定）
- 不修改 `frontend/src/components/stages/group-drag-zone.tsx`（已稳定）

## 实现规格

### 四种操作的交互设计

#### 1. 确认归组 (confirm)

**触发**：归组卡片上的 "确认" 按钮（仅 candidate 状态可见）

**流程**：
1. 点击 "确认" → 调用 `PUT /api/groups/{group_id}/confirm`，请求体: `{ projectId }`
2. 成功后更新该归组状态为 `confirmed`
3. 归组卡片显示绿色 "已确认" 标签
4. 已确认的归组不再显示 "确认" 按钮

**约束**：
- 仅 `status == "candidate"` 时可确认

#### 2. 拆分归组 (split)

**触发**：归组卡片上的 "拆分" 按钮（成员 >= 2 时可见）

**流程**：
1. 点击 "拆分" → 弹出 GroupSplitDialog
2. 对话框中展示该归组的所有成员
3. 用户通过勾选将成员分为两组（至少两组，每组至少一个成员）
4. 点击 "确认拆分" → 调用 `PUT /api/groups/{group_id}/split`
5. 成功后刷新归组列表

**约束**：
- 必须拆为至少 2 组
- 每组至少 1 个成员
- 拆分后新组状态为 `candidate`

#### 3. 手工合并 (merge)

**触发**：全局操作区的 "合并选中" 按钮（选中 >= 2 个归组时可见）

**流程**：
1. 用户在归组列表中勾选多个归组
2. 点击 "合并选中" → 确认对话框
3. 确认后 → 调用 `POST /api/projects/{project_id}/grouping/merge`
4. 成功后刷新归组列表

**约束**：
- 至少选中 2 个归组
- 合并后新组状态为 `candidate`

#### 4. 标记不可比 (not_comparable)

**触发**：归组卡片上的 "标记不可比" 按钮

**流程**：
1. 点击 → 确认对话框（"标记为不可比后，该归组将不参与比价"）
2. 确认后 → 调用 `PUT /api/groups/{group_id}/not-comparable`，请求体: `{ projectId }`
3. 成功后归组卡片显示红色 "不可比" 标签

**约束**：
- 已标记不可比的归组不参与后续比价

### components/stages/group-split-dialog.tsx

```tsx
/**
 * GroupSplitDialog — 拆分归组对话框
 *
 * Props:
 * - group: CommodityGroup — 要拆分的归组
 * - open: boolean
 * - onClose: () => void
 * - onConfirm: (newGroups: string[][]) => void
 *
 * 内部状态：
 * - memberAssignments: Map<string, number> — 每个成员分配到的组编号
 *   默认：前半成员分到组 1，后半成员分到组 2
 *
 * 展示：
 * - 左右两列或上下两块（组 1 和组 2）
 * - 每个成员行有单选/下拉选择分到哪个组
 * - "添加组" 按钮允许拆为 3+ 组
 * - 底部显示各组成员数量
 *
 * 验证：
 * - 至少 2 个组
 * - 每个组至少 1 个成员
 * - 所有成员都已分配
 */
```

### group-candidate-list.tsx 修改

每个归组卡片增加操作按钮行：

```tsx
// 操作按钮区域
<div className="flex gap-2 mt-2">
  {/* 确认按钮 — 仅 candidate 状态 */}
  {group.status === "candidate" && (
    <button onClick={() => onConfirm(group.id, group.projectId)}
            className="text-sm bg-green-500 text-white px-3 py-1 rounded">
      确认
    </button>
  )}

  {/* 拆分按钮 — 成员 >= 2 */}
  {group.memberCount >= 2 && group.status === "candidate" && (
    <button onClick={() => openSplitDialog(group)}
            className="text-sm bg-yellow-500 text-white px-3 py-1 rounded">
      拆分
    </button>
  )}

  {/* 标记不可比 — 非 not_comparable 状态 */}
  {group.status !== "not_comparable" && (
    <button onClick={() => onMarkNotComparable(group.id, group.projectId)}
            className="text-sm bg-red-500 text-white px-3 py-1 rounded">
      不可比
    </button>
  )}

  {/* 选中复选框 — 用于合并 */}
  <input type="checkbox"
         checked={selectedGroupIds.includes(group.id)}
         onChange={() => toggleSelect(group.id)} />
</div>

// 状态标签
{group.status === "confirmed" && (
  <span className="bg-green-100 text-green-700 text-xs px-2 py-1 rounded">已确认</span>
)}
{group.status === "not_comparable" && (
  <span className="bg-red-100 text-red-700 text-xs px-2 py-1 rounded">不可比</span>
)}
```

### grouping-stage.tsx 修改

全局合并操作：

```tsx
// 合并按钮（选中 >= 2 个归组时显示）
{selectedGroupIds.length >= 2 && (
  <button onClick={handleMerge}
          className="bg-blue-500 text-white px-4 py-2 rounded">
    合并选中 ({selectedGroupIds.length} 个)
  </button>
)}
```

### 错误处理

- API 调用失败时 → Toast 提示错误信息
- 网络错误 → "操作失败，请重试" 提示
- 拆分验证失败（少于 2 组或空组）→ 对话框内提示，不允许提交

## 测试与验收

### 门禁命令

```bash
cd frontend
pnpm lint                    # exit 0
pnpm tsc --noEmit            # exit 0
```

### 手动验收

- [ ] candidate 状态的归组显示 "确认" / "拆分" / "不可比" 按钮
- [ ] confirmed 状态的归组不显示 "确认" 按钮
- [ ] not_comparable 状态的归组不显示 "不可比" 按钮
- [ ] 点击 "确认" → 状态变为 confirmed，显示绿色标签
- [ ] 点击 "拆分" → 弹出对话框，可将成员分为多组
- [ ] 拆分对话框验证：每组至少 1 个成员，至少 2 组
- [ ] 选中 2+ 个归组后 "合并选中" 按钮可见
- [ ] 点击 "合并选中" → 确认后归组合并为一个
- [ ] 点击 "不可比" → 确认后显示红色标签
- [ ] 所有操作后归组列表自动刷新
- [ ] API 调用失败时显示错误提示

**断言清单：**

| 断言 | 预期 |
|------|------|
| `pnpm lint` | exit 0 |
| `pnpm tsc --noEmit` | exit 0 |
| 确认操作 → status 变为 confirmed | UI 更新 |
| 拆分操作 → 产生 2+ 新组 | 列表刷新 |
| 合并操作 → 多组合为一组 | 列表刷新 |
| 不可比操作 → status 变为 not_comparable | UI 更新 |
| 拆分对话框空组验证 | 提交被阻止 |

## 提交

```bash
git add frontend/src/components/stages/group-candidate-list.tsx \
       frontend/src/components/stages/group-split-dialog.tsx \
       frontend/src/components/stages/grouping-stage.tsx
git commit -m "Phase 3.7: 归组操作交互 — 确认/拆分对话框/合并选中/标记不可比"
```
