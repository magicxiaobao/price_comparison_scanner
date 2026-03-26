# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**三方比价支出依据扫描工具**（Three-Party Price Comparison Scanner）— 完全本地运行的桌面端采购比价审计辅助工具。帮助采购、审计、财务人员处理多家供应商报价文件，完成文件导入、表格提取、字段标准化、商品归组、项目需求符合性审查（可选）、基础比价和 Excel 审计底稿导出。

## 技术栈

| 层级 | 技术 | 版本要求 |
|------|------|----------|
| 桌面壳 | Tauri | 2.x |
| 前端 | React + TypeScript + Tailwind CSS | React 19+, TS 5.x |
| 表格组件 | TanStack Table | 8.x |
| 拖拽 | dnd-kit | 6.x |
| 状态管理 | Zustand | 5.x |
| 后端 | FastAPI (Python Sidecar) | Python 3.11+, FastAPI 0.115+ |
| PDF 解析 | pdfplumber + pypdf | MIT / BSD |
| Word/Excel | python-docx + openpyxl + pandas | MIT |
| 模糊匹配 | rapidfuzz | 3.15+ |
| 数据库 | SQLite3（内置） | 每项目独立 project.db |
| Excel 导出 | openpyxl | 3.1+ |
| OCR（可选） | PaddleOCR + PaddlePaddle | 独立安装模块 |
| 前端包管理 | pnpm | 9+ |
| 后端包管理 | uv 或 pip | — |
| 打包 | Tauri bundler + PyInstaller | — |

所有依赖必须支持商业使用（许可证清单见 PRD 附录 B）。

## 项目结构

```
price_comparison_scanner/
├── CLAUDE.md                    # 本文件
├── .mcp.json                    # MCP 服务器配置
├── mcp/
│   └── openapi-contract/        # OpenAPI MCP 服务（接口契约查询）
│       ├── server.py
│       └── pyproject.toml
├── docs/
│   ├── requirements/            # 需求文档
│   │   └── PRD-MVP-v1.md       # PRD v1.3
│   ├── design/                  # 设计文档
│   │   ├── technical-architecture.md      # 技术架构 v1.4
│   │   ├── commodity-grouping-algorithm.md # 归组算法 v1.0
│   │   └── acceptance-test-datasets.md    # 验收数据集 v1.0
│   ├── api/                     # 接口契约
│   │   └── openapi.json         # 后端自动生成的 OpenAPI 规范
│   └── prompts/                 # Agent 初始化提示词
│       └── leader-init.md       # Leader 角色恢复提示词
├── frontend/                    # Tauri + React 前端
│   ├── src/                     # React 源码
│   │   ├── app/                 # 页面
│   │   ├── components/          # 组件
│   │   ├── lib/                 # API client, utils
│   │   ├── stores/              # Zustand stores
│   │   └── types/               # TypeScript 类型定义
│   ├── src-tauri/               # Tauri Rust 配置和代码
│   │   ├── binaries/            # sidecar 可执行文件（打包时放入）
│   │   ├── tauri.conf.json
│   │   └── src/main.rs          # sidecar 启动/监控/端口管理/session token
│   ├── package.json
│   └── pnpm-lock.yaml
├── backend/                     # Python FastAPI 后端
│   ├── main.py                  # FastAPI 应用入口
│   ├── api/                     # API 路由
│   ├── services/                # 业务服务（ProjectService 等）
│   ├── engines/                 # 核心引擎（DocumentParser、RuleEngine 等）
│   ├── models/                  # Pydantic 数据模型（JSON 字段 schema）
│   ├── db/                      # SQLite 操作层
│   ├── requirements.txt
│   └── tests/
└── ocr-module/                  # OCR 可选模块（独立打包）
```

## 开发命令

```bash
# ── 后端 ──
cd backend
pip install -r requirements.txt           # 安装依赖（或 uv pip install -r requirements.txt）
uvicorn main:app --host 127.0.0.1 --port 17396 --reload  # 启动开发服务器

# ── 前端 ──
cd frontend
pnpm install                              # 安装依赖
pnpm dev                                  # 启动 Vite 开发服务器（不含 Tauri）

# ── Tauri 完整开发模式 ──
cd frontend
pnpm tauri dev                            # 启动 Tauri + 自动拉起 sidecar

# ── 生产打包 ──
cd backend
pyinstaller --onefile --name backend-<target-triple> main.py  # 打包 sidecar
cd frontend
pnpm tauri build                          # 打包桌面安装包

# ── 生成接口契约 ──
cd backend
python -c "
import json
from main import app
spec = app.openapi()
with open('../docs/api/openapi.json', 'w') as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)
"
```

## 接口契约（OpenAPI MCP）

后端与前端通过 `docs/api/openapi.json` 作为接口契约，由 MCP 服务实时提供给 Agent 查询。

### 工作原理

```
backend-dev 开发后端路由
  ↓
FastAPI 自动生成 openapi.json → docs/api/openapi.json
  ↓
openapi-contract MCP 服务 (watchdog 实时监控文件变化)
  ↓
frontend-dev 通过 MCP 工具查询接口契约
  ├── search_operations("standardize") → 搜索相关 API
  ├── get_operation("POST", "/api/projects/{id}/standardize") → 查看参数、请求体、响应
  ├── get_schema("StandardizedRow") → 查看数据模型定义
  └── list_tags() → 查看所有 API 分组
```

### MCP 工具列表（8 个）

| 工具 | 用途 |
|------|------|
| `reload_spec` | 强制重新加载 openapi.json |
| `list_tags` | 列出所有 API 标签（router 分组） |
| `list_operations` | 列出所有 API 操作摘要 |
| `search_operations` | 按关键字搜索 API 操作 |
| `get_operation` | 获取完整操作定义（参数、请求体、响应） |
| `get_schema` | 获取数据模型定义 |
| `list_schemas` | 列出所有数据模型名称 |
| `get_api_summary` | API 概览（操作数、标签分布） |

### 生成 openapi.json

```bash
cd backend
python -c "
import json
from main import app
spec = app.openapi()
with open('../docs/api/openapi.json', 'w') as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)
"
```

### 配置

MCP 服务在 `.mcp.json` 中配置，Claude Code 启动时自动加载：

```json
{
  "mcpServers": {
    "price-comparison-openapi": {
      "command": "uv",
      "args": ["run", "--directory", "mcp/openapi-contract", "python", "server.py"],
      "env": { "OPENAPI_PATH": "docs/api/openapi.json" }
    }
  }
}
```

### 接口契约工作流

```
backend-dev 完成 API 路由后:
  1. 生成 openapi.json: python -c "..." > docs/api/openapi.json
  2. MCP 服务自动检测文件变化并重载
  3. Leader 通知 frontend-dev: "接口契约已更新，请通过 MCP 查询"
  4. frontend-dev 使用 MCP 工具:
     - search_operations("comparison") → 找到比价相关 API
     - get_operation("POST", "/api/projects/{id}/comparison/generate") → 查看请求体和响应
     - get_schema("ComparisonResult") → 获取字段定义
  5. frontend-dev 严格按契约实现 API 调用和类型定义
  6. reviewer 对照 openapi.json 审查前后端一致性
```

**强制规则**：backend-dev 每次新增或修改 API 路由后，必须重新生成 openapi.json 并提交。frontend-dev 实现 API 调用前必须先通过 MCP 工具查询接口定义，不可凭假设编码。

## MCP 服务使用说明

### Context7（库文档查询）

**用途**：查询外部库/框架的官方文档、API 用法和最佳实践。

**使用条件**：
- 使用不熟悉的库 API 时（如 pdfplumber 表格提取、TanStack Table 配置、dnd-kit 拖拽、Tauri sidecar API）
- 需要确认库的最新用法或参数签名时
- 遇到库相关的报错需要查文档时

**使用方式**：
1. 先用 `resolve-library-id` 查找库的 Context7 ID
2. 再用 `get-library-docs` 获取特定主题的文档

**强制规则**：
- backend-dev 首次使用 pdfplumber / python-docx / openpyxl / rapidfuzz / pandas 的非常见 API 时，必须先通过 Context7 确认用法
- frontend-dev 首次使用 TanStack Table / dnd-kit / Zustand / Tauri API 时，必须先通过 Context7 确认用法
- 不要凭记忆猜测 API 参数，Context7 查询成本很低

### DeepWiki（技术问题查询）

**用途**：查询 GitHub 开源项目的架构、实现细节和技术问题。

**使用条件**：
- 需要了解某个开源项目的内部实现机制时（如 Tauri sidecar 机制的实现细节）
- 遇到复杂技术问题需要参考已有项目的解决方案时
- 需要理解某个库的设计决策或架构时

**使用方式**：
1. 用 `read_wiki_structure` 查看项目文档结构
2. 用 `read_wiki_contents` 查看具体文档内容
3. 用 `ask_question` 直接提问

**强制规则**：
- 遇到 Tauri sidecar 相关的技术难题时，优先通过 DeepWiki 查询 `tauri-apps/tauri` 仓库
- 遇到 FastAPI 异步任务、中间件等高级用法时，可通过 DeepWiki 查询 `tiangolo/fastapi`

## API 设计规范

- 所有 API 前缀：`/api/`
- 项目上下文显式化：`/api/projects/{id}/...`
- 资源级操作：`/api/files/{id}`、`/api/groups/{id}`
- Swagger 文档：`http://127.0.0.1:17396/docs`
- 安全：所有请求必须携带 `Authorization: Bearer <session_token>`
- 绑定地址：必须绑定 `127.0.0.1`，禁止 `0.0.0.0`
- 异步任务：耗时操作返回 `task_id`，前端轮询 `GET /api/tasks/{id}/status`
- 错误响应：`{ "detail": "..." }`（FastAPI 默认）
- TEXT 类型主键：所有实体使用 UUID 字符串

## 数据库约定

- 引擎：SQLite3（Python 内置），每项目独立 `project.db`
- 打开数据库时必须执行：`PRAGMA foreign_keys = ON`
- 所有写操作使用事务保护
- 状态字段使用 CHECK 约束
- 外键使用 ON DELETE CASCADE
- 数据库版本通过 `schema_version` 表管理
- JSON 字段通过 Pydantic model 统一序列化/反序列化，不允许各模块直接拼 JSON
- 全局 JSON 文件写操作采用原子替换（写临时文件 → fsync → rename）

## 前端约定

- 路由：React Router（Tauri 单页应用）
- 状态管理：Zustand（ProjectStore、RuleStore）
- 表格：TanStack Table（标准化预览、比价结果）
- 拖拽：dnd-kit（归组调整）
- 样式：Tailwind CSS
- API 调用：`src/lib/api.ts` 统一封装，自动携带 session token 和端口
- 组件：自定义组件放 `src/components/` 目录

## 语言约定

- **对话语言**：始终使用中文进行交流和讨论
- **文档语言**：所有文档（CLAUDE.md、设计文档、注释文档等）使用中文编写
- **Git 提交信息**：使用中文编写 commit message
- **代码**：变量名、函数名、类名等标识符使用英文；代码内注释视情况可用中文

## 代码规范

- Python：类型注解必须，async/await 一致，Pydantic v2 风格
- TypeScript：strict 模式，接口优先于 type alias
- 不要添加不必要的注释 — 代码应自描述
- 不要过度抽象 — 简单直接优于精巧设计
- 每个 commit 聚焦单一职责
- 所有依赖新增时同步更新 PRD 附录 B 许可证清单

---

## Team 开发工作流

### 角色职责分离

```
用户（你）
  ↕ 讨论需求
Leader（Claude Code 主进程）
  │  职责：需求分析、计划制定、任务分派、进度管理
  │  不做：写代码、代码审查
  │
  ├── reviewer       → 代码审查 + QA 审查
  ├── backend-dev    → Python 后端 + 核心引擎
  └── frontend-dev   → React 前端 + Tauri 壳
```

### Team 成员（3 个）

| Agent Name | Type | 职责 |
|------------|------|------|
| `reviewer` | general-purpose | 对照设计文档检查实现、代码质量审查、前后端契约一致性审查、提修复建议 |
| `backend-dev` | general-purpose | FastAPI 路由、核心引擎（DocumentParser/RuleEngine/TableStandardizer/CommodityGrouper/ComplianceEvaluator/PriceComparator/ReportGenerator）、TaskManager、SQLite 操作层、openapi.json 生成 |
| `frontend-dev` | general-purpose | Tauri 壳（sidecar 启动/监控/端口管理/session token）、React 页面（5 阶段工作台 + 问题清单 + 规则管理）、Zustand Store、TanStack Table、dnd-kit 归组交互、打包配置 |

### Leader 职责边界

**Leader 做：**
- 与用户 `brainstorming` 讨论需求
- `writing-plans` 生成实施计划
- `executing-plans` 按计划执行
- `subagent-driven-development` 任务分派
- `dispatching-parallel-agents` 并行任务调度
- TaskCreate 创建任务 + 设置依赖
- 分派任务给 Agent（SendMessage）
- 接收完成通知 → 通知 reviewer 审查
- 根据审查结果创建修复任务或关闭任务
- `verification-before-completion` 最终验证
- `finishing-a-development-branch` 完成收尾
- 向用户汇报进度

**Leader 不做：**
- 不写实现代码
- 不做代码审查（交给 reviewer）
- 不直接修改 backend/ 或 frontend/ 源文件

### 工作流程（每次新需求）

```
1. 用户提需求
2. Leader: brainstorming（与用户讨论确认）
3. Leader: writing-plans（生成实施计划）
4. Leader: TaskCreate × N（创建任务 + blockedBy 依赖）
5. Leader: dispatching-parallel-agents / subagent-driven-development（分派任务）
6. Agent 开发 → 完成 → 汇报 Leader
7. Leader → SendMessage 通知 reviewer 审查（requesting-code-review）
8. reviewer 审查（receiving-code-review）→ 通过/提修复建议
9. 有问题 → Leader 创建修复任务 → 回到步骤 6
10. 无问题 → 下一 Wave
11. 所有 Wave 完成 → Leader: verification-before-completion
12. Leader: finishing-a-development-branch
13. Leader 向用户汇报结果
```

### Agent 协作规则

1. **任务分配**：Leader 通过 TaskCreate + SendMessage 分配，Agent 不自行认领
2. **完成汇报**：Agent 完成后 TaskUpdate(completed) + SendMessage 通知 Leader
3. **审查流程**：Leader 通知 reviewer → reviewer 审查 → 反馈给 Leader
4. **问题上报**：遇到阻塞通过 SendMessage 通知 Leader
5. **修复闭环**：reviewer 发现问题 → Leader 创建修复任务 → Agent 修复 → reviewer 再审
6. **契约遵守**：frontend-dev 实现 API 调用前必须先读取 openapi.json，不可凭假设编码
7. **设计文档优先**：所有实现必须对照设计文档（PRD + 技术架构 + 归组算法），偏离时先和 Leader 确认
8. **MCP 优先查文档**：使用不熟悉的库 API 时，必须先通过 Context7 / DeepWiki 查询，不凭记忆猜测

### Agent Skill 分配与强制约束

每个 Agent 在 spawn 时通过 prompt 指定必须使用的 skill。**标注为「强制」的 skill 在对应场景下必须调用，不可跳过。**

#### Leader（主进程）

| Skill | 类型 | 触发条件 |
|-------|------|----------|
| `brainstorming` | **强制** | 任何创建新功能、新模块前必须先 brainstorming |
| `writing-plans` | **强制** | 开始多步骤实现任务前必须先生成计划 |
| `executing-plans` | **强制** | 有已批准计划时按计划执行 |
| `subagent-driven-development` | **强制** | 分派任务给 Agent 时 |
| `dispatching-parallel-agents` | **强制** | 存在 2+ 个无依赖的独立任务时 |
| `verification-before-completion` | **强制** | 声称工作完成前必须执行验证 |
| `finishing-a-development-branch` | **强制** | 实现完成、测试通过后决定如何集成 |
| `requirements-analyst` | 推荐 | 需求模糊时进行结构化分析 |

#### reviewer

| Skill | 类型 | 触发条件 |
|-------|------|----------|
| `review` | **强制** | 每次审查任务必须使用 |
| `receiving-code-review` | **强制** | 收到审查反馈时，严格验证而非盲目同意 |
| `simplify` | **强制** | 每次审查时检查代码是否可简化 |
| `scan` | **强制** | 涉及安全相关代码时（API 认证、文件路径处理、SQLite 操作） |
| `root-cause-analyst` | 推荐 | 发现复杂 bug 或系统性问题时 |

#### backend-dev

| Skill | 类型 | 触发条件 |
|-------|------|----------|
| `python-engineering` | **强制** | 所有 Python 代码编写和修改 |
| `backend-architect` | **强制** | 设计新服务、修改数据模型或 API 结构时 |
| `test-driven-development` | **强制** | 实现新功能前必须先写测试 |
| `systematic-debugging` | **强制** | 遇到 bug 或测试失败时，禁止猜测式修复 |

**backend-dev MCP 强制规则**：
- 首次使用 pdfplumber / python-docx / openpyxl / rapidfuzz / pandas 的非常见 API → **必须**先用 Context7 查文档
- 遇到 FastAPI 异步任务、中间件高级用法 → **推荐**用 DeepWiki 查询 `tiangolo/fastapi`

#### frontend-dev

| Skill | 类型 | 触发条件 |
|-------|------|----------|
| `frontend-design` | **强制** | 创建新页面或组件时 |
| `test-driven-development` | **强制** | 实现新功能前必须先写测试 |
| `systematic-debugging` | **强制** | 遇到 bug 或测试失败时 |
| `complex-api-integration-expert` | **强制** | 对接后端 API 时，必须先读取 openapi.json |
| `form-field-mapping-expert` | **强制** | 实现表单（需求标准录入、规则编辑、手工修正）时 |
| `webapp-testing` | 推荐 | 验证前端功能时 |
| `acejou27-shadcn-ui` | 推荐 | 需要查询 shadcn 组件用法时 |

**frontend-dev MCP 强制规则**：
- 首次使用 TanStack Table / dnd-kit / Zustand / Tauri API → **必须**先用 Context7 查文档
- 遇到 Tauri sidecar 机制技术难题 → **必须**用 DeepWiki 查询 `tauri-apps/tauri`

### 新会话恢复

如果需要在新的 Claude Code 会话中恢复 Leader 角色：

```
请阅读以下文件并恢复 Leader 角色：
- CLAUDE.md
- docs/prompts/leader-init.md
- docs/requirements/PRD-MVP-v1.md
- docs/design/technical-architecture.md

然后 TeamCreate("price-comparison") 并检查 TaskList 继续工作。
```

详细的 Leader 初始化提示词见：`docs/prompts/leader-init.md`

---

## 实施计划文档规范

实施计划存放在 `docs/plans/` 目录下，采用三层文档结构：

```
docs/plans/
├── <日期>-<功能名>-master-plan.md    ← 总排期 + 全局约束
├── phase-N/
│   ├── phase-spec.md                ← Phase 级规格：目标、边界、目录规范、门禁、完成标准
│   └── task-N.M-<名称>.md           ← 任务级规格：输入、输出、禁止修改、实现规格、验收断言
└── ...
```

### 文档优先级

**task-spec > phase-spec > master-plan**。当内容冲突时，以更细粒度的文档为准。

### task-spec 必须包含的章节

| 章节 | 内容 |
|------|------|
| 输入条件 | 前置任务完成状态、所需文件/API 就绪状态 |
| 输出物 | 精确文件路径（创建/修改） |
| 禁止修改 | 不得修改的文件/目录 |
| 实现规格 | 接口签名、代码骨架、关键逻辑 |
| 测试与验收 | fixture、机器可判定的断言、门禁命令 |
| 提交 | commit message 模板 |

### 执行约束

- Agent 执行任务时**严格限于 task-spec 定义的范围**，不得越权重构
- 若需修改 task-spec「禁止修改」范围外的文件，须先向 Leader 报告
- 每个任务提交前须通过工程门禁（后端 `ruff + mypy + pytest`，前端 `eslint + tsc`）
- 后端 API 变更后须运行 `python scripts/generate_openapi.py` 并提交变更

### 新增实施计划

新增功能的实施计划遵循相同结构：创建 `docs/plans/<日期>-<功能名>-master-plan.md` + 对应的 `phase-N/` 子目录。已完成的计划保留在原处，不归档。

---

## 关键文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 项目指南 | `CLAUDE.md` | 本文件 |
| PRD | `docs/requirements/PRD-MVP-v1.md` | v1.3 — 产品需求（含符合性模块） |
| 技术架构 | `docs/design/technical-architecture.md` | v1.4 — 架构、数据模型、API、页面骨架 |
| 归组算法 | `docs/design/commodity-grouping-algorithm.md` | v1.0 — 相似度公式、阈值、品牌别名表 |
| 验收数据集 | `docs/design/acceptance-test-datasets.md` | v1.0 — 5 套测试数据及预期结果 |
| 接口契约 | `docs/api/openapi.json` | 后端自动生成，前端开发依据 |
| MVP 实施计划 | `docs/plans/2026-03-26-mvp-implementation-master-plan.md` | 6 Phase、54 个任务的总排期 |
| Leader 提示词 | `docs/prompts/leader-init.md` | 新会话恢复 Leader 角色 |
