# Frontend Plan to Phase Tasks Mapping

> 用途：本文件用于把 `2026-03-27-frontend-workbench-implementation-plan.md` 与 `docs/plans/phase-*` 目录下的既有任务做一一映射。  
> 原则：`phase-*` 目录仍然是后续执行时的主任务来源；本文件只负责说明执行顺序和任务归属，不替代 phase 文档本身。

## 1. 使用方式

后续执行前端开发时，建议这样理解两套文档：

- `docs/plans/phase-*`：
  - 负责定义具体任务
  - 负责定义修改文件、接口、验收标准
  - 仍然是执行时的主文档
- `docs/plans/2026-03-27-frontend-workbench-implementation-plan.md`：
  - 负责定义执行顺序
  - 负责结合当前仓库真实状态进行前端批次安排
  - 解决“当前前端起点”和“原始 phase 顺序”不完全一致的问题

结论：后续还是按 phase 任务执行，只是执行顺序按本映射进行调整。

## 2. 映射总表

| 新实施计划任务包 | 对应 phase 任务 | 关系说明 |
|---|---|---|
| Task A: 工作台壳层与应用级页面对齐 | `phase-5/task-5.2-stage-navigation.md` + UI 原型基线 + 现有首页/规则管理页 | 主要是提前执行 Phase 5 中与工作台壳层相关的前端部分，不等于提前完成整个 Phase 5 |
| Task B: Phase 3 归组前端接入 | `phase-3/task-3.5-candidate-list-ui.md` + `task-3.6-dnd-kit-drag.md` + `task-3.7-confirm-split-merge.md` | 原样执行，是当前最适合接真接口的任务集 |
| Task C: 问题面板、阶段状态、dirty 传播前端化 | `phase-4/task-4.10-problem-panel-ui.md` + `phase-5/task-5.2-stage-navigation.md` | 属于跨 phase 的前端状态层任务，建议在归组接完后提前做 |
| Task D: Phase 4 UI 骨架与类型预留 | `phase-4/task-4.8-compliance-stage-ui.md` + `task-4.9-comparison-stage-ui.md` | 先做 UI 骨架、store 和类型预留，不等于 Phase 4 前端完全完成 |
| Task E: Phase 4/5 联调与最终验收 | `phase-4` 剩余后端联调相关任务 + `phase-5/task-5.1` ~ `task-5.6` | 等 Phase 4 后端 ready 后再进入正式联调、sidecar、打包、验收 |

## 3. 详细映射

### 3.1 Task A: 工作台壳层与应用级页面对齐

对应来源：

- `docs/plans/phase-5/task-5.2-stage-navigation.md`
- `docs/design/ui/home`
- `docs/design/ui/workbench-shell`
- `docs/design/ui/app-preferences`
- `docs/design/ui/rule-management`

这部分为什么要提前：

- 当前 `frontend/src/app/project-workbench.tsx` 还是早期容器，只是把导入和标准化顺序堆叠。
- 如果不先做工作台壳层，后续 Phase 3、4 的页面都会在错误容器上继续生长，返工成本高。

这部分从 `task-5.2-stage-navigation.md` 中吸收什么：

- 五阶段导航结构
- 阶段状态展示
- dirty 提示入口
- 工作台中阶段切换的前端容器结构

这部分不包含什么：

- 不包含 Phase 5 的 sidecar、打包、E2E、最终验收
- 不意味着 Phase 5 被提前“完成”

执行时建议参考：

- [task-5.2-stage-navigation.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-5/task-5.2-stage-navigation.md)

### 3.2 Task B: Phase 3 归组前端接入

对应来源：

- `docs/plans/phase-3/task-3.5-candidate-list-ui.md`
- `docs/plans/phase-3/task-3.6-dnd-kit-drag.md`
- `docs/plans/phase-3/task-3.7-confirm-split-merge.md`

这是最标准、最直接的一组映射，不需要重解释。

建议执行顺序：

1. `task-3.5-candidate-list-ui.md`
2. `task-3.6-dnd-kit-drag.md`
3. `task-3.7-confirm-split-merge.md`

原因：

- 3.5 先把归组列表和详情结构搭起来
- 3.6 再接拖拽交互
- 3.7 最后补齐确认、拆分、合并、不可比

执行时建议参考：

- [task-3.5-candidate-list-ui.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-3/task-3.5-candidate-list-ui.md)
- [task-3.6-dnd-kit-drag.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-3/task-3.6-dnd-kit-drag.md)
- [task-3.7-confirm-split-merge.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-3/task-3.7-confirm-split-merge.md)

### 3.3 Task C: 问题面板、阶段状态、dirty 传播前端化

对应来源：

- `docs/plans/phase-4/task-4.10-problem-panel-ui.md`
- `docs/plans/phase-5/task-5.2-stage-navigation.md`

为什么跨 phase：

- 问题面板在产品上属于 Phase 4 的 UI 任务
- 但阶段状态、dirty banner、阶段导航属于工作台壳层的基础设施
- 从当前前端实现顺序看，这两部分放在一起做更合理

建议拆法：

- 先完成阶段状态徽标、dirty banner、导航状态同步
- 再实现右侧问题面板和问题项点击逻辑
- 证据详情先做右侧抽屉壳层，不等待 Phase 4 真实数据

执行时建议参考：

- [task-4.10-problem-panel-ui.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-4/task-4.10-problem-panel-ui.md)
- [task-5.2-stage-navigation.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-5/task-5.2-stage-navigation.md)

### 3.4 Task D: Phase 4 UI 骨架与类型预留

对应来源：

- `docs/plans/phase-4/task-4.8-compliance-stage-ui.md`
- `docs/plans/phase-4/task-4.9-comparison-stage-ui.md`

这部分的关键约束：

- 先做 UI 结构
- 先做组件边界、类型、store 和 mock 数据
- 不把“后端未完成”误写成“前端任务不可启动”

建议执行顺序：

1. `task-4.8-compliance-stage-ui.md`
2. `task-4.9-comparison-stage-ui.md`

原因：

- 比价页依赖符合性阶段的存在感和状态语义
- 先把符合性空状态与矩阵态做出来，再补比价页更顺

执行时建议参考：

- [task-4.8-compliance-stage-ui.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-4/task-4.8-compliance-stage-ui.md)
- [task-4.9-comparison-stage-ui.md](/Users/a1234/ai/learn2026/price_comparison_scanner/docs/plans/phase-4/task-4.9-comparison-stage-ui.md)

### 3.5 Task E: Phase 4/5 联调与最终验收

对应来源：

- `docs/plans/phase-4/task-4.1-compliance-crud.md`
- `docs/plans/phase-4/task-4.3-compliance-api.md`
- `docs/plans/phase-4/task-4.5-comparison-api.md`
- `docs/plans/phase-4/task-4.7-problems-api.md`
- `docs/plans/phase-4/task-4.12-openapi-update.md`
- `docs/plans/phase-5/task-5.1-tauri-sidecar.md`
- `docs/plans/phase-5/task-5.2-stage-navigation.md`
- `docs/plans/phase-5/task-5.3-ocr-placeholder.md`
- `docs/plans/phase-5/task-5.4-e2e-testing.md`
- `docs/plans/phase-5/task-5.5-production-build.md`
- `docs/plans/phase-5/task-5.6-final-acceptance.md`

这部分何时开始：

- 必须等 Phase 4 后端能力真实落地
- 必须等前端 Task D 的页面骨架已稳定

这部分本质上就是：

- 把 Task D 中的 mock/预留换成真接口
- 再进入 Phase 5 的 sidecar、E2E、打包、验收

## 4. 推荐的实际执行顺序

后续如果你要“仍按 phase 文档执行”，推荐按下面顺序跑：

1. `phase-5/task-5.2-stage-navigation.md`
   - 只先执行工作台壳层、阶段导航、dirty 提示相关部分
2. `phase-3/task-3.5-candidate-list-ui.md`
3. `phase-3/task-3.6-dnd-kit-drag.md`
4. `phase-3/task-3.7-confirm-split-merge.md`
5. `phase-4/task-4.10-problem-panel-ui.md`
6. `phase-4/task-4.8-compliance-stage-ui.md`
7. `phase-4/task-4.9-comparison-stage-ui.md`
8. 等待 Phase 4 后端完成
9. 回到 `phase-4` 的 API / openapi / problems 联调相关任务
10. `phase-5/task-5.1`、`5.3`、`5.4`、`5.5`、`5.6`

## 5. 哪些 phase 任务当前不建议前端优先执行

### 5.1 Phase 5 中暂时不建议提前做的任务

- `task-5.1-tauri-sidecar.md`
- `task-5.3-ocr-placeholder.md`
- `task-5.4-e2e-testing.md`
- `task-5.5-production-build.md`
- `task-5.6-final-acceptance.md`

原因：

- 它们依赖更完整的前后端闭环
- 目前前端最高杠杆问题仍然是工作台壳层和归组阶段接入

### 5.2 Phase 4 中当前不建议前端单独先做的后端任务

- `task-4.1-compliance-crud.md`
- `task-4.2-compliance-matching.md`
- `task-4.3-compliance-api.md`
- `task-4.4-price-comparator.md`
- `task-4.5-comparison-api.md`
- `task-4.6-report-generator.md`
- `task-4.7-problems-api.md`
- `task-4.11-pydantic-models.md`
- `task-4.12-openapi-update.md`

原因：

- 这些主要是后端与接口文档任务
- 前端当前更适合先完成壳层、归组、问题面板和 Phase 4 UI 骨架

## 6. 最终结论

后续执行时，建议把本文件当作“前端 phase 任务导航图”使用：

- 真正执行时，仍然打开 `phase-*` 下的 task 文档逐个做
- 遇到“为什么先做这个 phase 的任务”时，以本映射为解释依据
- 遇到任务边界、文件清单、验收标准时，以原 phase task 文档为准

如果后续仓库状态变化，例如：

- Phase 4 后端已全部完成
- sidecar 已就绪
- 工作台壳层已经落地

则本映射应再更新一次。
