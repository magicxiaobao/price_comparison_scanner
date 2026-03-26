# Task 5.2: 阶段状态导航 + 失效提示 UI

## 输入条件

- Phase 4 全部完成，5 个阶段的页面组件均已实现
- `frontend/src/app/project-workbench.tsx` 存在（工作台页面）
- `frontend/src/stores/project-store.ts` 存在（包含 `stage_statuses` 状态）
- 后端 `StageStatuses` 模型已定义（Phase 0），包含各阶段状态字段
- 失效传播机制（`_propagate_dirty()`）已在 Phase 2 实现

## 输出物

- 创建: `frontend/src/components/stage-navigation.tsx`（阶段导航组件）
- 创建: `frontend/src/components/stage-dirty-banner.tsx`（失效提示横幅）
- 修改: `frontend/src/app/project-workbench.tsx`（集成导航组件）
- 修改: `frontend/src/stores/project-store.ts`（添加阶段切换逻辑，若尚未有）

## 禁止修改

- 不修改 `backend/` 目录下任何文件
- 不修改 `frontend/src-tauri/` 目录
- 不修改已有的 5 个阶段组件内部逻辑（`ImportStage`、`StandardizeStage`、`GroupingStage`、`ComplianceStage`、`ComparisonStage`）
- 不修改 `docs/api/openapi.json`

## 实现规格

### 阶段状态定义

```typescript
// 复用 StageStatuses 类型（已在 types/project.ts 中定义）
// 每个阶段的状态值：
type StageStatus = 'pending' | 'completed' | 'dirty' | 'skipped';
```

### StageNavigation 组件

```tsx
// frontend/src/components/stage-navigation.tsx

interface StageNavigationProps {
  projectId: string;
  currentStage: number;          // 0-4，当前选中阶段
  onStageChange: (stage: number) => void;
  stageStatuses: {
    import: StageStatus;
    standardize: StageStatus;
    grouping: StageStatus;
    compliance: StageStatus;
    comparison: StageStatus;
  };
}

// 5 个阶段的 Tab 定义
const STAGES = [
  { key: 'import',       label: '导入文件',   icon: '📁', index: 0 },
  { key: 'standardize',  label: '标准化',     icon: '📐', index: 1 },
  { key: 'grouping',     label: '商品归组',   icon: '🔗', index: 2 },
  { key: 'compliance',   label: '符合性审查', icon: '✅', index: 3 },
  { key: 'comparison',   label: '比价导出',   icon: '📊', index: 4 },
];
```

#### 状态视觉映射

| 状态 | 样式 | 说明 |
|------|------|------|
| `pending` | 灰色背景 + 灰色文字 | 尚未开始 |
| `completed` | 绿色背景/边框 + 绿色勾号 | 已完成 |
| `dirty` | 橙色背景/边框 + 警告图标 | 上游数据已变更，需重新计算 |
| `skipped` | 灰色虚线边框 + 跳过标记 | 用户主动跳过（仅符合性审查可跳过） |

#### 交互逻辑

- 所有阶段 Tab 均可点击（不严格线性限制）
- 点击任意阶段 → 调用 `onStageChange(index)` → 工作台切换显示对应阶段组件
- 当前选中阶段高亮显示（蓝色下边框/背景）

### StageDirtyBanner 组件

```tsx
// frontend/src/components/stage-dirty-banner.tsx

interface StageDirtyBannerProps {
  stageName: string;              // 当前阶段名称
  dirtyReason?: string;           // 失效原因描述
  onRecalculate?: () => void;     // 重新计算回调
}
```

- 当当前阶段状态为 `dirty` 时，在阶段内容区顶部显示橙色横幅
- 横幅内容：「上游数据已变更，当前 {stageName} 结果可能已失效，建议重新计算」
- 提供「重新计算」按钮（如果该阶段支持重新计算操作）

### 工作台集成

```tsx
// frontend/src/app/project-workbench.tsx 中集成

// 顶部：阶段导航
<StageNavigation
  projectId={projectId}
  currentStage={currentStage}
  onStageChange={setCurrentStage}
  stageStatuses={project.stage_statuses}
/>

// 内容区：根据 currentStage 显示对应组件
{currentStage === 0 && <ImportStage ... />}
{currentStage === 1 && (
  <>
    {stageStatuses.standardize === 'dirty' && (
      <StageDirtyBanner stageName="标准化" onRecalculate={handleReStandardize} />
    )}
    <StandardizeStage ... />
  </>
)}
// ... 其余阶段类似
```

### 样式要求

- 使用 Tailwind CSS，不引入额外 CSS 文件
- 导航栏使用 `flex` 横向排列，响应式
- Tab 之间使用连接线或箭头表示流程顺序
- 状态切换使用过渡动画（Tailwind `transition` 类）

## 测试与验收

### 前端门禁

```bash
cd frontend
pnpm lint      # exit 0
pnpm tsc --noEmit  # exit 0
```

### 手动验证

```
1. 打开项目工作台
   - 新建项目 → 5 个阶段全部显示为 pending（灰色）
   - 导航栏横向显示 5 个 Tab

2. 阶段切换
   - 点击任意阶段 Tab → 内容区切换到对应组件
   - 当前选中 Tab 高亮

3. 状态显示
   - 完成导入后 → 导入阶段变为 completed（绿色）
   - 完成标准化后 → 标准化变为 completed
   - 修改导入数据（重新上传）→ 标准化/归组/比价变为 dirty（橙色+警告图标）

4. 失效提示
   - 切换到 dirty 状态的阶段 → 顶部显示橙色横幅
   - 横幅显示「上游数据已变更」提示
   - 点击「重新计算」→ 触发对应操作

5. 跳过符合性审查
   - 符合性审查阶段显示为 skipped → 灰色虚线边框
   - 可正常跳过进入比价导出阶段
```

## 提交

```bash
git add frontend/src/components/stage-navigation.tsx frontend/src/components/stage-dirty-banner.tsx frontend/src/app/project-workbench.tsx
git commit -m "Phase 5.2: 阶段状态导航 + 失效提示 UI（5 阶段 Tab + dirty 横幅）"
```
