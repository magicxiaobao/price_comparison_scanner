> ⚠️ **DEPRECATED — 本文件仅供历史参考，不作为 agent 执行依据。**
> 各 Phase 的正式规格已迁移到 `phase-N/phase-spec.md` 和 `phase-N/task-*.md`。
> **当本文件与 phase-spec / task-spec 内容冲突时，以 phase-spec / task-spec 为准。**

# MVP 全量实施计划（Master Plan）

> **文档定位：** 总排期与总任务图。不直接作为 agent 执行依据，每个 Phase 有独立的 phase-spec，每个 Task 有独立的 task-spec。
>
> **文档优先级：** task-spec > phase-spec > master-plan。当内容冲突时，以更细粒度的文档为准。
>
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 按 6 个实施阶段（Phase），从零搭建三方比价支出依据扫描工具 MVP，实现完整的 5 阶段工作台闭环（导入 → 标准化 → 归组 → 符合性审查 → 比价导出）。

**架构:** Tauri 2.x 桌面壳 + React 19 前端 + Python FastAPI Sidecar 后端。前后端通过本地 HTTP JSON API 通信（sidecar 仅绑定 `127.0.0.1`，session token 认证）。数据存储使用 SQLite（项目级）+ JSON 文件（全局配置/规则）。前后端通过 `openapi.json` 作为接口契约（自动生成 + 脚本校验）。

**技术栈:** Tauri 2.x, React 19, TypeScript 5.x, Tailwind CSS 4.x, TanStack Table 8.x, dnd-kit 6.x, Zustand 5.x, FastAPI 0.115+, Python 3.11+, SQLite3, pdfplumber, python-docx, openpyxl, pandas, rapidfuzz

---

## 文档层级

```
docs/plans/
├── master-plan.md              ← 本文件（总排期 + 总任务图 + 全局约束）
├── phase-0/
│   ├── phase-spec.md           ← Phase 级规格：目标、边界、工程门禁、目录规范、完成标准
│   ├── task-0.1-xxx.md         ← 任务级规格：输入、输出、fixture、断言、禁止修改范围
│   └── ...
├── phase-1/
│   ├── phase-spec.md
│   └── ...
└── ...
```

**task-spec 标准模板：**

```markdown
# Task N.M: [任务名称]

## 输入条件
- 前置任务完成状态
- 所需文件/数据/API 就绪状态

## 输出物
- 创建: `exact/path/to/file`
- 修改: `exact/path/to/file` (修改范围说明)

## 禁止修改
- 不得修改的文件/目录

## 实现规格
- 具体技术要求、接口签名、数据结构

## 测试与验收
- fixture 文件
- 断言条件（机器可判定）
- 门禁检查命令

## 提交
- commit message 模板
```

---

## 全局工程约束

### 安全约束

- 后端 **必须绑定 `127.0.0.1`**，禁止 `0.0.0.0`
- 所有非公开 API 必须校验 `Authorization: Bearer <session_token>`
- **禁止在后端添加 CORSMiddleware**。开发模式下通过 Vite proxy（`/api → http://127.0.0.1:17396`）解决跨域。生产模式下前端内嵌在 Tauri WebView 中，不经过 CORS

### 工程门禁

每个任务提交前，agent 必须执行以下检查并确认全部通过：

**后端门禁：**
```bash
cd backend
ruff check .                    # lint（零警告）
mypy . --ignore-missing-imports # 类型检查（零错误）
pytest -x -q                    # 测试（全部通过）
```

**前端门禁：**
```bash
cd frontend
pnpm lint                       # ESLint（零警告）
pnpm tsc --noEmit               # TypeScript 类型检查（零错误）
pnpm test --run                 # 测试（全部通过，若有测试）
```

**契约门禁（后端 API 变更时）：**
```bash
cd backend
python scripts/generate_openapi.py
git diff --exit-code docs/api/openapi.json  # 若有 diff，必须提交更新
```

### 依赖管理

- 后端：`requirements.txt` 锁定具体版本（`fastapi==0.115.x`），CI 可复现
- 后端开发依赖：`requirements-dev.txt`（pytest, httpx, anyio, pytest-anyio, ruff, mypy）
- 前端：`pnpm-lock.yaml` 提交到仓库，安装时使用 `pnpm install --frozen-lockfile`
- 新增依赖时必须检查许可证，更新 PRD 附录 B

### OpenAPI 契约自动化

- `backend/scripts/generate_openapi.py`：自动生成 `docs/api/openapi.json`
- 后端每次新增/修改 API 路由后，**必须**运行此脚本并提交变更
- MCP 服务（openapi-contract）通过 watchdog 实时监控文件变化，自动重载

### 目录规范

后端和前端的目录结构在各自的 Phase 0 task-spec 中定义，一经确立，后续 Phase **禁止自行调整目录结构**（如需调整须回到 phase-spec 修改并经 Leader 确认）。

### 禁止越权重构

Agent 在执行任务时，**严格限于 task-spec 定义的输出物和修改范围**：

- 不得"顺手"重构 task-spec 未涉及的模块
- 不得修改 task-spec 中"禁止修改"列出的文件
- 若发现当前任务需要修改禁止范围之外的文件才能完成，**必须先通过 SendMessage 向 Leader 报告理由**，经确认后方可操作
- 不得自行添加 task-spec 未要求的依赖库
- 不得自行更改工程门禁配置（ruff/mypy/eslint/tsconfig）

---

## 分阶段总览

| Phase | 名称 | 目标 | 前置依赖 | 任务数 |
|-------|------|------|----------|--------|
| **0** | 最小技术闭环 | 前后端跑通：sidecar 启动 → health → 项目 CRUD → 前端首页连通 + 工程门禁就绪 | 无 | 8 |
| **1** | 文件导入（工作台第一步） | 文件上传解析、供应商确认、表格选择、TaskManager 异步框架 | Phase 0 | 10 |
| **2** | 规则引擎 + 标准化（工作台第二步） | 全局规则管理、列名映射、字段标准化、手工修正、AuditLog、失效传播 | Phase 1 | 10 |
| **3** | 商品归组（工作台第三步） | 归一化、多因子打分、候选归组、确认/拆分/合并、拖拽交互 | Phase 2 | 8 |
| **4** | 符合性审查 + 比价导出（工作台第四步 + 第五步） | 需求标准、符合性匹配、比价计算、异常检测、Excel 4-Sheet 导出、问题清单 | Phase 3 | 12 |
| **5** | 集成联调 + 打包 + 验收 | Tauri sidecar 生命周期、阶段导航 UI、验收数据集验证、生产打包、OCR 接口占位验证 | Phase 4 | 6 |

**总计：约 54 个任务**

---

## Phase 0：最小技术闭环

**目标：** 跑通一条极薄垂直链路 — 后端 health API 可响应、项目可创建/查询、前端首页可连通后端并展示项目列表。同时确立工程门禁和目录规范。

**不包含（下沉到业务 Phase）：**
- 全量 Pydantic 模型（→ 各 Phase 按需定义）
- TaskManager 异步框架（→ Phase 1）
- AuditLogService（→ Phase 2）
- Zustand Store 完整接口（→ Phase 1+）

**任务列表：**

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 0.1 | 后端项目骨架 + 工程门禁 | backend-dev | 无 |
| 0.2 | Session Token 认证中间件 | backend-dev | 0.1 |
| 0.3 | SQLite 数据库层 + Schema 初始化 | backend-dev | 0.1 |
| 0.4 | 项目 CRUD API（最小版） | backend-dev | 0.2, 0.3 |
| 0.5 | OpenAPI 自动生成脚本 + 首次契约 | backend-dev | 0.4 |
| 0.6 | 前端项目骨架 + 工程门禁 + 目录规范 | frontend-dev | 无 |
| 0.7 | 前端 API Client 封装 | frontend-dev | 0.6 |
| 0.8 | 首页 — 项目列表 + 新建项目（连通后端） | frontend-dev | 0.4, 0.7 |

**Phase 0 完成标准（机器可判定）：**

```bash
# 后端
cd backend
ruff check . && mypy . --ignore-missing-imports && pytest -x -q
curl -s http://127.0.0.1:17396/api/health | jq .status  # → "ok"
curl -s -H "Authorization: Bearer test" http://127.0.0.1:17396/api/projects | jq .  # → []

# 前端
cd frontend
pnpm lint && pnpm tsc --noEmit
pnpm dev  # 首页可访问，显示空项目列表，新建项目可成功

# 契约
test -f docs/api/openapi.json  # openapi.json 存在
```

**详细规格：** 见 `docs/plans/phase-0/phase-spec.md`

---

## Phase 1：文件导入（工作台第一步）

**目标：** 用户可以上传供应商文件（xlsx/docx/pdf），系统异步解析出表格，用户确认供应商名称并选择参与比价的表格。

**本 Phase 引入：**
- TaskManager 异步框架
- DocumentParser 引擎（Excel / Word / PDF-L1 解析器）
- 文件导入相关 Pydantic 模型（SupplierFile, RawTable）
- 前端 ImportStage 组件

**PDF OCR 策略：** 仅实现 L1 结构化提取 + `_is_ocr_available()` 能力检测占位。L2/L3 接口签名定义但内部返回 "OCR 未安装" 提示。OCR 实际集成移到 Phase 5。

**任务列表：**

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 1.1 | TaskManager 异步任务框架 + 任务状态 API | backend-dev | Phase 0 |
| 1.2 | DocumentParser — Excel 解析器 | backend-dev | Phase 0 |
| 1.3 | DocumentParser — Word 解析器 | backend-dev | Phase 0 |
| 1.4 | DocumentParser — PDF 结构化解析器（L1 only） | backend-dev | Phase 0 |
| 1.5 | 文件导入 API + 供应商确认 API + 表格选择 API | backend-dev | 1.1-1.4 |
| 1.6 | 文件导入相关 Pydantic 模型 | backend-dev | Phase 0 |
| 1.7 | 前端 ImportStage — 文件上传 + 解析进度 | frontend-dev | 1.5 |
| 1.8 | 前端 ImportStage — 供应商确认 + 表格选择 | frontend-dev | 1.5 |
| 1.9 | 前端 ProjectStore 扩展（阶段状态） | frontend-dev | 1.7 |
| 1.10 | 更新 openapi.json + reviewer 审查 | backend-dev | 1.5 |

**Phase 1 完成标准：**
- 上传 .xlsx / .docx / .pdf 文件 → 异步解析成功 → 返回 RawTable 列表
- 供应商名称可确认、表格可选择/取消
- 任务进度可查询、可取消
- 前端 ImportStage 可完整操作
- 工程门禁全部通过

---

## Phase 2：规则引擎 + 标准化（工作台第二步）

**目标：** 用户可以管理全局规则，对导入的表格执行字段标准化，预览和手工修正标准化结果。

**本 Phase 引入：**
- RuleEngine 引擎
- TableStandardizer 引擎
- AuditLogService（手工修正需要留痕）
- 失效传播机制（`_propagate_dirty()`）
- 标准化相关 Pydantic 模型（StandardizedRow, SourceLocation, Rule 等）
- 前端 RuleManagement 页面 + StandardizeStage

> **注意：** 本章节的任务编号和描述与 `docs/plans/phase-2/phase-spec.md` 保持一致。详细规格见各 task-spec 文件。当内容冲突时，以 phase-spec 和 task-spec 为准。

**任务列表：**

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 2.1 | AuditLogService 操作留痕 | backend-dev | Phase 1 |
| 2.2 | RuleEngine — 规则加载/管理/冲突解决 | backend-dev | Phase 1 |
| 2.3 | 规则管理 API（10 个端点） | backend-dev | 2.2 |
| 2.4 | TableStandardizer — 字段映射 + 值标准化 | backend-dev | 2.2 |
| 2.5 | 标准化 API + 手工修正 API + 失效传播 | backend-dev | 2.1, 2.4, 2.6 |
| 2.6 | 标准化相关 Pydantic 模型 | backend-dev | Phase 1 |
| 2.7 | 前端 RuleManagement 页面 | frontend-dev | 2.3, 2.9 |
| 2.8 | 前端 StandardizeStage — 预览 + 可编辑表格 + 手工修正 | frontend-dev | 2.5 |
| 2.9 | 前端 RuleStore | frontend-dev | 2.3 |
| 2.10 | 更新 openapi.json + reviewer 审查 | backend-dev | 2.5 |

**Phase 2 完成标准：**
- 规则 CRUD + 导入导出 + 测试 + 模板 全流程可用
- 标准化可执行，结果可预览
- 手工修正可保存，下游阶段标记 dirty
- 内置默认模板可加载
- AuditLog 可查（手工修正有留痕）

---

## Phase 3：商品归组（工作台第三步）

**目标：** 系统基于标准化结果生成候选归组，用户可以确认、拆分、合并、拖拽调整归组。

**本 Phase 引入：**
- CommodityGrouper 引擎（归一化 + 多因子打分 + 硬约束）
- 品牌别名表 + 噪音词表
- 归组相关 Pydantic 模型（CommodityGroup, GroupMember）
- 前端 GroupingStage（候选列表 + dnd-kit 拖拽）

**任务列表：**

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 3.1 | CommodityGrouper — 文本归一化 + 品牌别名 + 噪音词 | backend-dev | Phase 2 |
| 3.2 | CommodityGrouper — 多因子打分 + 硬约束 + 候选归组生成 | backend-dev | 3.1 |
| 3.3 | 归组 API（生成 + 确认 + 拆分 + 合并） | backend-dev | 3.2 |
| 3.4 | 归组相关 Pydantic 模型 | backend-dev | Phase 2 |
| 3.5 | 前端 GroupingStage — 候选归组列表（置信度分层） | frontend-dev | 3.3 |
| 3.6 | 前端 GroupingStage — dnd-kit 拖拽归组交互 | frontend-dev | 3.5 |
| 3.7 | 前端 GroupingStage — 确认/拆分/合并/标记不可比 | frontend-dev | 3.5 |
| 3.8 | 更新 openapi.json + reviewer 审查 | backend-dev | 3.3 |

**Phase 3 完成标准：**
- 归组候选可生成，按置信度分层展示
- 5 条禁止自动归组硬约束生效
- 确认/拆分/合并/拖拽 操作可用
- 操作触发下游失效传播

---

## Phase 4：符合性审查 + 比价导出（工作台第四步 + 第五步）

**目标：** 用户可以（可选）录入需求标准并进行符合性匹配，执行比价计算，检测异常，导出 Excel 审计底稿，查看跨阶段问题清单。

**本 Phase 引入：**
- ComplianceEvaluator 引擎（可选模块）
- PriceComparator 引擎
- ReportGenerator 引擎
- 符合性 + 比价相关 Pydantic 模型
- 前端 ComplianceStage + ComparisonStage + ProblemPanel

**任务列表：**

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 4.1 | ComplianceEvaluator — 需求标准 CRUD + 导入导出 | backend-dev | Phase 3 |
| 4.2 | ComplianceEvaluator — 符合性匹配（keyword/numeric/manual） | backend-dev | 4.1 |
| 4.3 | 符合性 API（匹配 + 矩阵 + 确认 + 可接受标记） | backend-dev | 4.2 |
| 4.4 | PriceComparator — 比价计算 + 异常检测 + 双口径最低价 | backend-dev | Phase 3 |
| 4.5 | 比价 API | backend-dev | 4.4 |
| 4.6 | ReportGenerator — 4 Sheet Excel 导出 | backend-dev | 4.3, 4.5 |
| 4.7 | 待处理问题清单 API | backend-dev | 4.3, 4.5 |
| 4.8 | 前端 ComplianceStage — 需求录入 + 符合性矩阵 + 证据面板 | frontend-dev | 4.3 |
| 4.9 | 前端 ComparisonStage — 比价结果 + 异常高亮 + 导出 | frontend-dev | 4.5, 4.6 |
| 4.10 | 前端 ProblemPanel — 跨阶段问题清单 | frontend-dev | 4.7 |
| 4.11 | 符合性 + 比价相关 Pydantic 模型 | backend-dev | Phase 3 |
| 4.12 | 更新 openapi.json + reviewer 审查 | backend-dev | 4.7 |

**Phase 4 完成标准：**
- 符合性审查可选（不录入需求时可跳过，直接进入比价）
- 比价计算正确（全量最低价 + 有效最低价）
- 异常检测完整（税价/单位/币种/缺项/必填缺失）
- Excel 导出 4 Sheet（或 3 Sheet，无需求标准时）
- 问题清单跨阶段聚合展示

---

## Phase 5：集成联调 + 打包 + 验收

**目标：** Tauri sidecar 完整生命周期管理、阶段状态导航 UI、验收数据集端到端验证、OCR 接口占位验证、生产打包。

**本 Phase 引入：**
- Tauri Rust 端 sidecar 管理（main.rs）
- 阶段导航 UI
- OCR 接口占位验证（确认 `_is_ocr_available()` + L2/L3 占位路径可达）

**任务列表：**

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 5.1 | Tauri Sidecar 集成（启动/监控/重启/端口/token/清理） | frontend-dev | Phase 4 |
| 5.2 | 阶段状态导航 + 失效提示 UI | frontend-dev | Phase 4 |
| 5.3 | OCR 接口占位验证 + 未安装时用户提示 | backend-dev | Phase 4 |
| 5.4 | 端到端联调（5 套验收数据集） | reviewer | 5.1, 5.2 |
| 5.5 | 生产打包（PyInstaller + Tauri bundler） | frontend-dev + backend-dev | 5.4 |
| 5.6 | 安装包验证 + 最终验收 | reviewer | 5.5 |

**Phase 5 完成标准：**
- Tauri sidecar 完整生命周期管理（启动/心跳/重启/安全模式/退出清理）
- 5 套验收数据集全部通过
- 安装包可正常安装和运行
- MVP 验收标准全部满足（PRD 第 10 节）
- OCR 未安装时有明确提示，不崩溃

---

## 并行化策略

| Phase | 可并行的任务 |
|-------|-------------|
| 0 | 后端（0.1-0.5）与前端（0.6-0.7）完全并行；0.8 等待 0.4 完成 |
| 1 | Excel/Word/PDF 解析器（1.2/1.3/1.4）可并行；前端 1.7/1.8 等待 1.5 完成 |
| 2 | RuleEngine（2.2）与 AuditLog（2.1）可并行；前端 2.7/2.8 等待 API 就绪 |
| 3 | 归一化（3.1）先行，打分（3.2）依赖 3.1；前端 3.5/3.6 等待 3.3 |
| 4 | Compliance（4.1-4.3）与 PriceComparator（4.4-4.5）可并行；ReportGenerator（4.6）依赖两者 |

## Wave 执行模式

每个 Phase 作为一个 Wave：
1. **后端先行**（提供 API + 更新契约）
2. **前端跟进**（通过 MCP 查询契约 → 对接 API）
3. **reviewer 审查**（代码质量 + 契约一致性 + 设计文档对照）
4. **修复闭环**（reviewer 反馈 → 创建修复任务 → 修复 → 再审）
5. **下一 Phase**
