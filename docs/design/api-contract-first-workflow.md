# API Contract-First 工作流

## 定位

这是仓库级**可选工作流**，用于在某些 Phase 中采用“接口契约先行、mock 先行、前后端并行”的开发方式。

- 本工作流**不默认启用**
- 只有当某个 `phase-spec`、任务编排文档或 Leader 指令**明确声明启用**时，Agent 才按本流程执行
- 未明确声明时，默认仍使用仓库现有工作流：后端实现 → 生成 `openapi.json` → 前端接入 → reviewer 验收

## 目的

- 缩短前端等待后端真实实现完成后才能开工的时间
- 提前冻结字段、枚举、错误语义和异步任务语义，减少前后端返工
- 降低 UI 设计/页面开发与后端重逻辑实现之间的冲突
- 让 reviewer 更早在“契约层”发现问题，而不是只在真实实现完成后补救

## 适用条件

适合启用本工作流的场景：

- 前后端并行收益高
- 页面或交互复杂，前端强依赖 API 结构
- 后端真实实现较重，但接口形状、错误语义和异步任务模型可以先稳定定义
- 当前 Phase 明确依赖 `docs/api/openapi.json` 作为前端开发基线

## 不适用条件

以下情况不建议启用：

- 业务规则仍在高频变化，接口语义尚未稳定
- 单人开发或改动范围很小，传统流程更简单
- mock 很难真实表达关键复杂度，反而会制造虚假稳定感
- 团队无法保证 `mock → openapi → 真实实现` 三者持续一致

## 标准流程

### Step 1：先定义模型与枚举

先定义本 Phase 使用的 Pydantic 模型、枚举值、错误响应形状、异步任务响应形状。

要求：

- 后端响应命名继续遵守项目统一 alias 策略
- API 边界字段命名遵守 camelCase 输出约定
- TypeScript 类型以最终契约为准，不允许额外猜字段

### Step 2：先定义路由契约

在 task-spec / phase-spec 中明确：

- path / method / path params / query params
- request body
- response body
- 错误码与错误语义
- 空结果、处理中、blocked/partial 等业务状态

这一步完成后，契约应当已经足够生成稳定的 `openapi.json`。

### Step 3：先实现受约束 mock

后端先交付可运行的 mock 实现，用于：

- 路由可访问
- 请求体验证可运行
- 响应结构与状态码可运行
- 前端可基于真实 path 进行联调

硬要求：

- mock 必须运行在**真实路由**上
- mock 使用**真实请求/响应结构**
- 不允许为前端额外开一套“临时测试接口”

### Step 4：生成并冻结 openapi.json

mock 路由稳定后，生成并冻结：

- `docs/api/openapi.json`

从这一刻起，前端正式以该契约为开发基线。

### Step 5：前端基于契约并行开发

frontend-dev 必须：

- 通过 MCP 查询 `openapi.json`
- 基于契约实现 API client、TS 类型、store、页面和交互
- 不得根据猜测补字段、改字段名或自行简化接口

### Step 6：后端逐步替换 mock 为真实实现

backend-dev 在不改变契约的前提下，将 mock 替换为真实仓库/服务/引擎实现。

允许替换的内容：

- 查询逻辑
- 事务与持久化逻辑
- 异步任务真实执行逻辑
- 引擎内部计算逻辑

不允许静默改变的内容：

- path
- request body
- response shape
- 枚举值
- 关键业务状态语义

### Step 7：Contract Regression Review

reviewer 需要验证：

- mock 与 openapi 一致
- 真实实现与 openapi 一致
- 前端消费方式与 openapi 一致
- 替换真实实现过程中没有引入字段漂移

### Step 8：真实实现验收

完成真实实现替换后，再按该 Phase 的正常 gate 执行：

- `ruff`
- `mypy`
- `pytest`
- 前端 `lint`
- 前端 `tsc`
- openapi 回归检查
- 手工联调 / 集成验收

## 硬规则

启用本工作流时，以下规则必须执行：

1. `docs/api/openapi.json` 是前端正式开工 gate
2. frontend-dev 实现前必须通过 MCP 查询契约，不得凭 task-spec 片段或记忆编码
3. mock 必须覆盖错误路径，不能只覆盖 happy path
4. 真实实现替换 mock 时，不得静默改契约；如需改契约，必须先更新 spec 并重新评审
5. API 边界字段命名遵守项目统一 alias/camelCase 约定
6. 每项目独立 `project.db` 的接口是否显式传 `projectId`，必须在契约阶段写死，后续不得临时变更
7. 同一个 Phase 内不得同时混用“未声明的 contract-first”与“默认工作流”

## 角色分工

### backend-contract-owner

负责：

- Pydantic 模型与枚举定义
- 路由契约与错误语义
- mock 路由实现
- `openapi.json` 初次冻结

### backend-impl-owner

负责：

- 用真实 repo/service/engine 替换 mock
- 保持契约不漂移
- 补真实实现测试

### frontend-dev

负责：

- 基于 MCP/openapi 实现 API client、TS 类型、store 和页面
- 在契约已冻结的基础上并行推进 UI 与交互
- 发现契约不足时，回推 spec/review，而不是自行改字段

### reviewer

负责：

- 审模型与契约是否闭环
- 审 mock 是否真实可用
- 审真实实现替换后契约是否回归
- 在 gate 点给出放行或阻塞结论

## Gate 建议

启用本工作流时，建议至少设置以下 gate：

- `G0`：模型与枚举冻结
- `G1`：mock 路由 + `openapi.json` 冻结
- `G2`：前端基于契约接入完成
- `G3`：真实实现替换完成，契约无漂移

没有通过 `G1`，前端不应正式开工。

## 在 Phase 中如何声明启用

某个 Phase 要使用本工作流时，应在对应 `phase-spec` 或任务编排文档中明确写出：

- 本 Phase 启用 `API Contract-First`
- 哪些任务属于“契约与 mock”
- `openapi.json` 在哪一波冻结
- 哪些前端任务可在 `G1` 后启动
- 哪些后端任务属于“真实实现替换”
- reviewer 的 gate 放在哪几个波次

## 与默认工作流的关系

- 本工作流是**可选补充方案**，不是默认方案
- 仓库默认仍使用“后端实现先行，再更新 openapi，再前端接入”的常规流程
- 只有当具体 Phase 明确声明启用时，Agent 才按本流程执行
