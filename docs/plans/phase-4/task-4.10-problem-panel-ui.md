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

### [C11-fix] ProblemGroup.type 完整枚举

| type 值 | label（显示名） | stage | 默认 severity |
|---------|----------------|-------|---------------|
| `unconfirmed_supplier` | 未确认供应商名称 | `import` | warning |
| `unmapped_field` | 未映射字段 | `normalize` | warning |
| `rule_conflict` | 规则冲突 | `normalize` | warning |
| `low_confidence_unconfirmed` | 低置信字段未确认 | `normalize` | warning |
| `missing_required_field` | 必填字段缺失 | `normalize` | warning |
| `unconfirmed_group` | 未确认归组项 | `grouping` | warning |
| `unconfirmed_compliance` | 未确认需求匹配 | `compliance` | warning |
| `mandatory_not_met` | 必选需求未满足 | `compliance` | **error** |
| `unclear_unconfirmed` | 无法判断且未确认 | `compliance` | warning |
| `partial_not_decided` | 部分符合但未判定可接受 | `compliance` | warning |
| `unit_mismatch` | 单位不一致异常 | `comparison` | **error** |
| `tax_basis_mismatch` | 税价口径异常 | `comparison` | **error** |

### [C11-fix] stage → icon 映射表

```typescript
const STAGE_ICON_MAP: Record<string, { icon: string; label: string }> = {
  import:     { icon: 'Upload',      label: '导入' },
  normalize:  { icon: 'Table',       label: '标准化' },
  grouping:   { icon: 'Group',       label: '归组' },
  compliance: { icon: 'ClipboardCheck', label: '符合性' },
  comparison: { icon: 'BarChart3',   label: '比价' },
};
// icon 值对应 lucide-react 图标名称
```

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
// 注意：后端使用 _CAMEL_CONFIG，API JSON 字段名为 camelCase

interface ProblemItem {
  id: string;
  stage: string;
  targetId: string;
  description: string;
  severity: 'warning' | 'error';
}

interface ProblemGroup {
  type: string;
  label: string;
  stage: string;
  severity: 'warning' | 'error';    // [M1-fix] 与后端 ProblemGroup 模型对齐
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

## Review Notes（审查发现的 Medium/Low 问题）

### 实现约束（开发时必须处理）

- **[M19] 问题面板刷新触发机制**：通过 `useEffect` 监听 ProjectStore 中的 stage status 变化（任何 stage_status 字段变化时触发 `refreshProblems`）。阶段 API 操作成功后，前端会刷新 project 状态，间接触发面板刷新。额外提供手动刷新按钮。
- **[M20] 问题项跳转定位**：点击问题项 → 调用 `ProjectStore.setActiveStage(item.stage)` 切换阶段标签页。不做行级滚动定位（MVP 限制），用户切换阶段后自行查找对应项。

### Reviewer 提醒

- **[Low] 面板宽度**：右侧侧边栏默认宽度 320px，折叠时仅显示一个带计数 badge 的图标按钮（24px）。
- **[Low] 问题分组排序**：按 stage 出现顺序排列（import → normalize → grouping → compliance → comparison），同 stage 内按 type 首字母排序。
