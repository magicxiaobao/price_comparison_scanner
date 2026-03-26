# Task 4.10: 前端 ProblemPanel — 跨阶段问题清单

## 输入条件

- Task 4.7 完成（问题清单 API 可用）
- openapi.json 已更新（problems API 部分）

## 输出物

- 创建: `frontend/src/components/stages/problem-panel.tsx`
- 修改: `frontend/src/lib/api.ts`（新增 problems API 调用）
- 修改: `frontend/src/stores/project-store.ts`（新增 refreshProblems 实现）
- 修改: `frontend/src/app/project-workbench.tsx`（接入 ProblemPanel 常驻面板）

## 禁止修改

- 不修改 `backend/`
- 不修改已有 stages 组件
- 不修改 `frontend/src/App.tsx` 路由配置

## 实现规格

**MCP 强制规则**：实现前必须通过 openapi-contract MCP 工具查询 problems API 响应结构。

### 组件结构

#### problem-panel.tsx

```
ProblemPanel
├── 折叠/展开控制
├── 总计数标题 "N 个待处理问题"
├── 按类型分组列表
│   ├── 问题组标题 + 计数 badge
│   │   ├── 阶段图标 (import/normalize/grouping/compliance/comparison)
│   │   └── 点击展开/折叠
│   └── 问题项列表
│       ├── 问题描述
│       ├── severity 图标 (warning 黄色 / error 红色)
│       └── 点击跳转按钮 → 切换到对应阶段
└── 全部清零时显示 "所有问题已处理，可导出" ✓
```

**交互行为：**
- 面板位置：工作台右侧侧边栏或顶部可折叠面板
- 默认折叠，显示总计数 badge
- 展开后按问题类型分组显示
- 每组可独立折叠/展开
- 点击问题项 → 自动切换到对应阶段并定位（通过 stage 字段）
- 阶段切换通过 ProjectStore 触发
- 问题数据在以下时机自动刷新：
  - 进入工作台
  - 完成任何阶段操作后
  - 手动刷新按钮

**样式：**
- error 类型：红色图标 + 红色计数 badge
- warning 类型：黄色图标 + 黄色计数 badge
- 各阶段图标区分（导入=上传图标，标准化=表格图标，归组=分组图标，符合性=检查图标，比价=比较图标）
- 全部清零时绿色对勾 + 提示文字

### api.ts 新增调用

```typescript
interface ProblemItem {
  id: string;
  stage: string;
  target_id: string;
  description: string;
  severity: 'warning' | 'error';
}

interface ProblemGroup {
  type: string;
  label: string;
  stage: string;
  count: number;
  items: ProblemItem[];
}

getProblems(projectId: string): Promise<ProblemGroup[]>
```

### project-store.ts 修改

完善 `refreshProblems` 方法，调用 `api.getProblems(id)` 并更新 `problems` 状态。

### project-workbench.tsx 修改

- 在工作台布局中添加 ProblemPanel
- 推荐位置：右侧侧边栏（可折叠），或顶部横幅（可折叠）
- ProblemPanel 接收当前 projectId
- 提供阶段切换回调函数，ProblemPanel 点击问题项时调用

## 测试与验收

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

**手动验证（需后端运行中）：**
- 工作台显示问题面板
- 面板默认折叠，显示总计数
- 展开后按类型分组显示
- 有未确认归组 → 显示「未确认归组项」组
- 有异常 → 显示对应异常组（红色 badge）
- 点击问题项 → 切换到对应阶段
- 确认操作后刷新 → 计数减少
- 所有问题清零 → 显示「所有问题已处理」

**断言清单：**

| 断言 | 预期 |
|------|------|
| `pnpm lint` | exit 0 |
| `pnpm tsc --noEmit` | exit 0 |
| 面板可折叠/展开 | 交互正常 |
| 按类型分组显示 | 结构正确 |
| 计数与实际项数一致 | count == items.length |
| 点击跳转 | 切换到对应阶段 |
| 全部清零 → 绿色提示 | 文案正确 |

## 提交

```bash
git add frontend/src/components/stages/problem-panel.tsx \
       frontend/src/lib/api.ts \
       frontend/src/stores/project-store.ts \
       frontend/src/app/project-workbench.tsx
git commit -m "Phase 4.10: ProblemPanel — 跨阶段问题清单面板(12类问题/分组/跳转/折叠/全清零提示)"
```
