# Task 3.6: 前端 GroupingStage — dnd-kit 拖拽归组交互

## 输入条件

- Task 3.5 完成（GroupingStage + GroupCandidateList 基础 UI 就绪）
- dnd-kit 6.x 已在 `package.json` 中声明

> **MCP 强制规则**：首次使用 dnd-kit API 时，**必须**先通过 Context7 查文档确认 `@dnd-kit/core` 和 `@dnd-kit/sortable` 的用法，特别是 `DndContext`、`useDraggable`、`useDroppable`、`DragOverlay` 的参数和事件处理。

## 输出物

- 创建: `frontend/src/components/stages/group-drag-zone.tsx`
- 修改: `frontend/src/components/stages/grouping-stage.tsx`（集成 DndContext）
- 修改: `frontend/src/components/stages/group-candidate-list.tsx`（成员行添加拖拽能力）

## 禁止修改

- 不修改 `backend/`
- 不修改 `frontend/src/types/grouping.ts`（已稳定）
- 不修改 `frontend/src/lib/api.ts`（已稳定）

## 实现规格

### 拖拽交互设计

**场景**：用户将一个商品行从归组 A 拖拽到归组 B，实现归组间成员移动。

**交互流程**：
1. 每个成员行 (`GroupMemberSummary`) 是一个 draggable 元素
2. 每个归组卡片是一个 droppable 区域
3. 拖拽开始时显示 DragOverlay（半透明的成员行副本）
4. 拖到目标归组上方时高亮目标区域
5. 放下时：
   - 调用 split API（从源组移除该行）
   - 如果目标是已有归组：调用 merge API 或直接更新成员
   - 刷新归组列表

**约束**：
- 已确认 (confirmed) 的归组不接受新成员拖入（需先取消确认或用合并操作）
- 不可比 (not_comparable) 的归组不接受拖入
- 归组只剩 1 个成员时不允许拖出（否则变成空组）

### components/stages/group-drag-zone.tsx

```tsx
/**
 * GroupDragZone — dnd-kit 拖拽区域
 *
 * 包裹在每个归组卡片外层，使其成为 droppable 目标。
 * 同时每个成员行是 draggable 元素。
 *
 * dnd-kit 核心组件使用：
 * - DndContext: 最外层上下文
 * - useDraggable: 成员行
 * - useDroppable: 归组卡片
 * - DragOverlay: 拖拽时的浮层
 */

interface GroupDragZoneProps {
  group: CommodityGroup;
  children: React.ReactNode;
  isDropTarget: boolean;  // 当前是否为拖拽目标（高亮）
}

// Draggable 成员行
interface DraggableMemberProps {
  member: GroupMemberSummary;
  groupId: string;       // 所属归组 ID
  isDragDisabled: boolean; // 归组只剩 1 个成员时禁用
}
```

### grouping-stage.tsx 修改

```tsx
/**
 * 集成 DndContext
 *
 * - 包裹 GroupCandidateList 在 DndContext 中
 * - onDragStart: 记录拖拽源（member + groupId）
 * - onDragEnd: 处理放下逻辑
 *   1. 如果放在同一组 → 不操作
 *   2. 如果放在另一组 → 执行移动：
 *      a. 从源组拆分出该成员
 *      b. 合并到目标组
 *      c. 刷新列表
 * - onDragCancel: 清除拖拽状态
 *
 * 状态：
 * - activeDragItem: { member, sourceGroupId } | null
 */
```

### 拖拽实现的 API 调用逻辑

成员移动通过单一原子 API 完成：

```
用户将成员 M 从归组 A 拖到归组 B：

1. 前端校验：A 成员数 > 1，B 状态非 confirmed/not_comparable
2. 调用 PUT /api/groups/{A}/move-member
   请求体: { projectId, targetGroupId: B.id, rowId: M.id }
3. 后端原子执行：从 A 移除 M → 添加 M 到 B → 失效传播
4. 刷新归组列表
```

无需前端编排多步 API 调用，不存在半完成状态风险。

### 视觉反馈

- 拖拽开始：源成员行变为半透明
- DragOverlay：跟随鼠标的成员行卡片（含供应商名、商品名）
- 悬停在可放置区域：目标归组卡片边框变为蓝色 `border-blue-500`
- 不可放置区域（confirmed/not_comparable）：无高亮
- 拖拽结束：恢复正常状态

## 测试与验收

### 门禁命令

```bash
cd frontend
pnpm lint                    # exit 0
pnpm tsc --noEmit            # exit 0
```

### 手动验收

- [ ] 成员行有拖拽手柄图标（grip/dots 图标）
- [ ] 拖拽开始时显示 DragOverlay
- [ ] 拖到可接受的归组上时目标高亮
- [ ] 放下后成员从源组移到目标组
- [ ] 归组只剩 1 个成员时该成员不可拖出
- [ ] confirmed 状态的归组不接受拖入
- [ ] not_comparable 状态的归组不接受拖入
- [ ] 拖拽后归组列表自动刷新
- [ ] 操作后下游阶段显示 dirty 提示

**断言清单：**

| 断言 | 预期 |
|------|------|
| `pnpm lint` | exit 0 |
| `pnpm tsc --noEmit` | exit 0 |
| dnd-kit 相关 import 无编译错误 | 通过 |
| 拖拽成员到另一归组 → 列表更新 | 成员归属变更 |
| 单成员归组 → 成员不可拖出 | 拖拽被禁用 |

## 提交

```bash
git add frontend/src/components/stages/group-drag-zone.tsx \
       frontend/src/components/stages/grouping-stage.tsx \
       frontend/src/components/stages/group-candidate-list.tsx
git commit -m "Phase 3.6: dnd-kit 拖拽归组交互 — 成员跨组移动 + 视觉反馈 + 约束校验"
```
