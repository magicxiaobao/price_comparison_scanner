# Frontend Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在当前已完成的 Phase 1、Phase 2 前端和已完成的 Phase 3 后端基础上，重构前端为统一的五阶段桌面工作台，并优先完成归组阶段联调，使现有导入与标准化能力自然迁移到新的工作台壳层中。  
**Architecture:** React + TypeScript + Zustand + React Router 的桌面式工作台架构；应用级页面与项目级工作台分离；工作台采用“项目头部 + 阶段导航 + 主工作区 + 可折叠问题面板 + 单一证据详情模式”的固定布局。  
**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Zustand, Axios, TanStack Table, dnd-kit, Tauri API

---

## 1. 当前状态结论

截至 2026-03-27，仓库中的真实状态如下：

- Phase 1、Phase 2 前端已存在基础实现：
  - 首页：`frontend/src/app/home-page.tsx`
  - 规则管理：`frontend/src/app/rule-management.tsx`
  - 导入阶段：`frontend/src/components/stages/import-stage.tsx`
  - 标准化阶段：`frontend/src/components/stages/standardize-stage.tsx`
- 当前工作台仍是早期容器：
  - `frontend/src/app/project-workbench.tsx`
  - 仅把导入和标准化阶段顺序堆叠渲染，尚未形成五阶段工作台。
- Phase 3 后端已完成并已出现在当前代码树中：
  - `backend/api/grouping.py`
  - `backend/services/grouping_service.py`
  - `backend/models/grouping.py`
  - `docs/api/openapi.json` 已包含归组接口。
- Phase 4 后端在当前代码树中尚未落地：
  - 当前未见 `backend/api/compliance.py`
  - 当前未见 `backend/services/compliance_service.py`
  - 当前未见 `backend/models/compliance.py`
  - 因此前端不应等待 Phase 4 完成后才开始整体重构。
- UI 原型基线已评审通过：
  - `docs/design/ui`
  - `docs/plans/2026-03-27-ui-prototype-design.md`
  - `docs/plans/2026-03-27-ui-prototype-review-summary.md`

结论：前端开发不应按原始 phase 编号机械推进，而应按“先壳层、再 Phase 3 联调、再 Phase 4 骨架、最后总体集成”的顺序推进。

## 2. 实施原则

### 2.1 壳层优先

先重构工作台壳层，再迁移阶段页面。不要先分别打磨单个阶段页面，否则后续还会返工到统一容器中。

### 2.2 已完成能力不回退

导入和标准化能力必须在新工作台壳层中完整保留，不允许因为 UI 重构导致已存在的业务链路不可用。

### 2.3 Phase 3 优先接真接口

归组阶段后端已 ready，应优先完成前后端联调，形成新的业务推进点。

### 2.4 Phase 4 先做 UI 骨架

在 Phase 4 后端未落地前，只做组件接口、布局、mock 数据和状态管理预留，不在前端硬编码假 API。

### 2.5 保持桌面工作台约束

实现必须继承已评审原型中的关键约束：

- 最小支持宽度先按 `1280px` 设计
- 问题面板在空间不足时默认可折叠
- MVP 只实现一种证据详情形态：`右侧抽屉`
- 表格优先支持固定列与横向滚动
- 比价页首屏信息层级受控，不堆过多摘要卡片

## 3. 总体任务拆分

本轮前端实施计划拆成五个任务包：

1. 工作台壳层与应用级页面对齐
2. Phase 3 归组前端接入
3. 问题面板、阶段状态、dirty 传播前端化
4. Phase 4 UI 骨架与类型预留
5. Phase 4/5 联调与最终验收

---

## 4. Task A: 工作台壳层与应用级页面对齐

### 4.1 目标

把当前散式页面入口重构成统一的桌面工作台骨架，并让首页、规则管理、应用偏好设置与评审通过的 UI 原型保持一致。

### 4.2 修改范围

- 修改：`frontend/src/App.tsx`
- 修改：`frontend/src/app/project-workbench.tsx`
- 修改：`frontend/src/app/home-page.tsx`
- 修改：`frontend/src/app/rule-management.tsx`
- 新增：`frontend/src/app/app-preferences.tsx`
- 新增：`frontend/src/components/workbench/stage-navigation.tsx`
- 新增：`frontend/src/components/workbench/stage-dirty-banner.tsx`
- 新增：`frontend/src/components/workbench/problem-panel-shell.tsx`
- 新增：`frontend/src/components/workbench/evidence-drawer-shell.tsx`

### 4.3 实现要求

- `App.tsx` 新增应用偏好设置路由。
- `project-workbench.tsx` 改造成统一容器：
  - 顶部项目栏
  - 阶段导航
  - 主工作区
  - 右侧问题面板壳层
  - 右侧证据抽屉壳层
- 先把已有的 `ImportStage`、`StandardizeStage` 嵌入主工作区。
- 首页视觉结构向 `docs/design/ui/home` 对齐。
- 规则管理页只做壳层与布局对齐，不在这一任务包中大改业务行为。
- 应用偏好设置按 `docs/design/ui/app-preferences` 建立真实页面。

### 4.4 验收标准

- 首页可进入：
  - 新建项目
  - 规则管理
  - 应用偏好设置
- 任意项目进入后，看到的是统一工作台，而不是导入/标准化页面堆叠。
- 导入和标准化现有功能仍可使用。
- 问题面板和证据抽屉即使先为空，也已具备稳定布局位置。

### 4.5 验证命令

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
pnpm build
```

---

## 5. Task B: Phase 3 归组前端接入

### 5.1 目标

基于已存在的归组后端接口，完成第三阶段的真实前后端联调，并把归组阶段接入工作台。

### 5.2 修改范围

- 新增：`frontend/src/types/grouping.ts`
- 新增：`frontend/src/stores/grouping-store.ts`
- 新增：`frontend/src/components/stages/grouping-stage.tsx`
- 新增：`frontend/src/components/stages/group-candidate-list.tsx`
- 新增：`frontend/src/components/stages/group-drag-zone.tsx`
- 新增：`frontend/src/components/stages/group-split-dialog.tsx`
- 修改：`frontend/src/lib/api.ts`
- 修改：`frontend/src/app/project-workbench.tsx`

### 5.3 接口范围

按 `docs/api/openapi.json` 与 `docs/plans/phase-3` 文档接入以下接口：

- `POST /api/projects/{project_id}/grouping/generate`
- `GET /api/projects/{project_id}/groups`
- `PUT /api/groups/{group_id}/confirm`
- `POST /api/groups/{group_id}/split`
- `POST /api/projects/{project_id}/grouping/merge`
- `PUT /api/groups/{group_id}/not-comparable`
- `PUT /api/groups/{group_id}/move-member`

### 5.4 实现要求

- 先完成候选组列表和详情面板。
- 再接入 dnd-kit 拖拽移动。
- 最后补齐确认、拆分、合并、标记不可比。
- 阶段状态从项目对象读取：
  - `grouping_status`
  - `compliance_status`
  - `comparison_status`
- 归组操作后刷新项目状态，驱动后续阶段 `dirty` 呈现。

### 5.5 验收标准

- 可以从工作台第三步触发“生成归组”。
- 可以查看候选组、未确认项、不可比项。
- 可以执行确认、拆分、合并、拖拽移动、标记不可比。
- 操作完成后前端状态与后端返回一致。
- 归组变更能反映到后续阶段状态。

### 5.6 验证命令

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
pnpm build
```

手动联调重点：

- 生成归组后列表刷新
- 拖拽后成员位置变化
- 拆分/合并后候选组数量与成员变化
- `grouping_status` 完成后阶段导航状态变化
- `compliance_status` / `comparison_status` 受影响时显示 dirty

---

## 6. Task C: 问题面板、阶段状态、dirty 传播前端化

### 6.1 目标

把问题清单和 dirty 状态从纯视觉占位提升为前端一等对象，为 Phase 4/5 做结构准备。

### 6.2 修改范围

- 新增：`frontend/src/types/problem.ts`
- 新增：`frontend/src/stores/workbench-store.ts`
- 新增：`frontend/src/components/workbench/problem-panel.tsx`
- 新增：`frontend/src/components/workbench/problem-item.tsx`
- 新增：`frontend/src/components/workbench/stage-status-badge.tsx`
- 修改：`frontend/src/app/project-workbench.tsx`
- 修改：`frontend/src/stores/project-store.ts`

### 6.3 实现要求

- `workbench-store` 管理：
  - 当前阶段
  - 右侧问题面板开合状态
  - 当前证据抽屉对象
  - 统一的 dirty banner 开关
- 问题来源初期允许分两类：
  - 已有真实问题源：导入、标准化、归组阶段返回的问题
  - 结构占位问题：Phase 4 之前用 mock 映射展示跨阶段位置
- 阶段导航要明确显示：
  - `pending`
  - `completed`
  - `dirty`
  - `skipped`

### 6.4 验收标准

- 右侧问题面板可折叠。
- 阶段导航状态与项目阶段状态一致。
- `dirty` 能通过 banner 和阶段导航同时体现。
- 问题项点击后能打开右侧证据抽屉壳层。

### 6.5 验证命令

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
```

---

## 7. Task D: Phase 4 UI 骨架与类型预留

### 7.1 目标

在 Phase 4 后端未落地前，先按已评审原型与 phase 设计文档搭出符合性、比价与导出、证据详情、问题清单等组件骨架。

### 7.2 修改范围

- 新增：`frontend/src/types/compliance.ts`
- 新增：`frontend/src/types/comparison.ts`
- 新增：`frontend/src/stores/compliance-store.ts`
- 新增：`frontend/src/stores/comparison-store.ts`
- 新增：`frontend/src/components/stages/compliance-stage.tsx`
- 新增：`frontend/src/components/stages/requirement-editor.tsx`
- 新增：`frontend/src/components/stages/requirement-importer.tsx`
- 新增：`frontend/src/components/stages/compliance-matrix.tsx`
- 新增：`frontend/src/components/stages/comparison-stage.tsx`
- 新增：`frontend/src/components/stages/comparison-table.tsx`
- 新增：`frontend/src/components/workbench/evidence-detail-panel.tsx`
- 新增：`frontend/src/components/workbench/anomaly-highlight.tsx`
- 新增：`frontend/src/components/workbench/export-button.tsx`
- 修改：`frontend/src/app/project-workbench.tsx`

### 7.3 实现要求

- 使用 mock 数据驱动布局，不伪造后端完成态。
- 明确区分符合性阶段两种状态：
  - 空状态
  - 矩阵状态
- 比价页必须预留双口径结果位：
  - 全量最低价
  - 有效最低价
- 证据详情统一走右侧抽屉，不实现底部面板。
- 问题面板与矩阵单元格、异常行、表格字段等点击入口结构先打通。

### 7.4 验收标准

- 可以在工作台中切换到：
  - 符合性空状态
  - 符合性矩阵骨架
  - 比价与导出骨架
- 布局与 `docs/design/ui` 原型对齐。
- 类型定义、store 接口和组件边界清晰，为后续 API 接入留出稳定接口。

### 7.5 验证命令

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
pnpm build
```

---

## 8. Task E: Phase 4/5 联调与最终验收

### 8.1 前置条件

以下后端能力在当前代码树尚未验证为已完成，因此本任务包必须在后端 ready 后再执行：

- 符合性接口
- 比价结果接口
- 导出接口
- 问题列表/证据详情相关接口

### 8.2 目标

把 Task D 中的骨架替换为真实接口联调，并完成最终工作台闭环。

### 8.3 预期修改范围

- 修改：`frontend/src/lib/api.ts`
- 修改：`frontend/src/types/compliance.ts`
- 修改：`frontend/src/types/comparison.ts`
- 修改：`frontend/src/stores/compliance-store.ts`
- 修改：`frontend/src/stores/comparison-store.ts`
- 修改：`frontend/src/components/stages/compliance-stage.tsx`
- 修改：`frontend/src/components/stages/comparison-stage.tsx`
- 修改：`frontend/src/components/workbench/problem-panel.tsx`
- 修改：`frontend/src/components/workbench/evidence-detail-panel.tsx`
- 修改：`frontend/src/app/project-workbench.tsx`

### 8.4 联调要求

- 接入符合性矩阵真实数据与确认/可接受操作。
- 接入比价结果生成与结果表展示。
- 接入导出操作与状态提示。
- 问题面板改为真实跨阶段问题聚合。
- 证据详情从真实对象入口打开，展示真实来源信息。

### 8.5 最终验收标准

- 首页 -> 新建项目 -> 工作台五阶段链路完整。
- 导入 -> 标准化 -> 归组 -> 符合性 -> 比价导出 可以按真实状态推进。
- 任何上游变更能触发下游 dirty。
- 比价页能够清楚展示：
  - 能否下结论
  - 为什么不能下结论
  - 是否可导出
- 问题面板与证据抽屉成为真实工作对象，而非纯视觉装饰。

### 8.6 验证命令

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
pnpm build
```

如果届时补齐自动化测试，再补：

```bash
cd frontend
pnpm test
```

---

## 9. 推荐开发顺序

按以下顺序推进，避免返工：

1. Task A: 工作台壳层与应用级页面对齐
2. Task B: Phase 3 归组前端接入
3. Task C: 问题面板、阶段状态、dirty 传播前端化
4. Task D: Phase 4 UI 骨架与类型预留
5. 等待 Phase 4 后端完成
6. Task E: Phase 4/5 联调与最终验收

## 10. 里程碑定义

### Milestone 1: Workbench Base

完成 Task A 后达成：

- 首页、规则管理、应用偏好设置与 UI 基线对齐
- 项目工作台成为统一容器
- 导入与标准化迁入新壳层

### Milestone 2: Grouping Live

完成 Task B 后达成：

- 归组阶段成为真实可操作阶段
- 前后端第一次形成新的端到端业务闭环

### Milestone 3: Workbench Statefulness

完成 Task C 后达成：

- 阶段状态、问题面板、dirty 传播从视觉原型进入真实前端状态管理

### Milestone 4: Phase 4 Ready Shell

完成 Task D 后达成：

- 符合性与比价页面结构稳定
- 等待后端即可联调，不再需要大范围 UI 重构

### Milestone 5: MVP Frontend Closure

完成 Task E 后达成：

- 前端达到 MVP 工作台闭环

---

## 11. 风险与应对

### 风险 1: 工作台壳层引入后，导入/标准化现有组件布局失稳

应对：

- 先做容器包裹与插槽，不同时重写两个阶段组件
- 优先保证功能不回退，再逐步对齐视觉细节

### 风险 2: 归组阶段状态复杂，拖拽和拆分同时引入会放大调试成本

应对：

- 先上候选组列表
- 再接拖拽
- 再接拆分/合并/不可比

### 风险 3: 提前做 Phase 4 页面，容易因后端字段变化返工

应对：

- 只锁组件边界和布局，不锁最终字段细节
- 类型以 phase 文档和 openapi 草案为参考，不做过度具体化

### 风险 4: 右侧问题面板和表格主区在窄桌面下冲突

应对：

- 先固定 `1280px` 为最小支持宽度
- 问题面板默认可折叠
- 表格支持横向滚动与固定关键列

## 12. 本计划对应的立即执行建议

如果下一步直接进入开发，建议从以下子任务开始：

1. 改造 `App.tsx` 与 `project-workbench.tsx`，建立工作台壳层
2. 新建 `app-preferences.tsx`，补齐应用级页面
3. 把首页与规则管理对齐到 `docs/design/ui`
4. 扩展 `lib/api.ts` 与 `types/grouping.ts`，准备接入归组 API
5. 开始实现 `grouping-stage.tsx`

这五步完成后，前端就会从“已有几个阶段页面”进入“真正可扩展的桌面工作台架构”。
