# Phase 0：最小技术闭环 — Phase Spec

> **文档优先级：** 本 phase-spec 及其下属 task-spec 的内容优先于 master-plan。若 master-plan 中有与本文档冲突的描述，以本文档为准。

## 目标

跑通一条极薄垂直链路：后端 health API 可响应 → 项目可创建/列表查询 → 前端首页可连通后端并展示项目列表。同时确立工程门禁、目录规范和接口契约自动化。

**不是** "所有底座一次做完"。Pydantic 全量模型、TaskManager、AuditLogService 等下沉到业务 Phase 按需引入。

## 边界

### 本 Phase 包含

- 后端 FastAPI 应用骨架 + health API
- Session Token 认证中间件（开发模式可跳过）
- SQLite 数据库层（连接管理 + 事务封装 + schema 初始化）
- 项目 CRUD（最小版：创建 + 列表 + 详情 + 删除）
- 项目相关 Pydantic 模型（仅 Project + StageStatuses，不含全量）
- OpenAPI 自动生成脚本 + 首次契约文件
- 后端工程门禁（ruff + mypy + pytest）
- 前端 Tauri + React + Vite 项目骨架
- 前端工程门禁（ESLint + TypeScript strict）
- 前端 API Client 封装（Axios + token/端口注入）
- 首页（新建项目 + 项目列表 + 规则管理入口占位）
- 前端基础路由（首页 / 工作台占位 / 规则管理占位）

### 本 Phase 不包含（明确排除）

- 全量 Pydantic 模型定义（→ 各 Phase 按需）
- TaskManager 异步任务框架（→ Phase 1）
- AuditLogService 操作留痕（→ Phase 2）
- Zustand Store 完整接口定义（→ Phase 1+）
- 文件上传/解析相关 API（→ Phase 1）
- 规则管理 API（→ Phase 2）
- CORS 中间件（开发时前端直连后端，通过 Vite proxy 解决跨域；不在后端加 CORS）

---

## 后端目录规范

Phase 0 确立以下目录结构，后续 Phase **禁止自行调整**（需经 Leader 确认）：

```
backend/
├── main.py                     # FastAPI 应用入口（app 创建 + 中间件注册 + router include）
├── config.py                   # 配置管理（端口、token、dev_mode、app_data 路径）
├── scripts/
│   └── generate_openapi.py     # OpenAPI 自动生成脚本
├── api/                        # API 路由层（仅路由 + 请求/响应编排，不含业务逻辑）
│   ├── __init__.py
│   ├── health.py               # GET /api/health
│   ├── projects.py             # /api/projects 相关
│   ├── middleware.py            # Session Token 认证
│   └── deps.py                 # 依赖注入（get_db, get_project_db 等）
├── services/                   # 业务服务层（协调引擎 + 数据库操作）
│   ├── __init__.py
│   └── project_service.py      # 项目 CRUD + 阶段状态管理
├── engines/                    # 核心引擎（纯业务算法，不依赖 FastAPI/DB）
│   └── __init__.py
├── models/                     # Pydantic 数据模型（请求/响应 + JSON 字段 Schema）
│   ├── __init__.py
│   └── project.py              # Project, StageStatuses（Phase 0 仅此文件）
├── db/                         # 数据库操作层
│   ├── __init__.py
│   ├── database.py             # Database 类（连接管理 + 事务）
│   ├── schema.sql              # 建表 SQL（完整 schema，一次建好）
│   └── project_repo.py         # 项目表 CRUD 操作
├── requirements.txt            # 生产依赖（锁定版本）
├── requirements-dev.txt        # 开发依赖（ruff, mypy, pytest 等）
├── pyproject.toml              # ruff + mypy 配置
└── tests/
    ├── __init__.py
    ├── conftest.py             # 测试 fixture（test client, temp db 等）
    ├── test_health.py
    ├── test_middleware.py
    ├── test_database.py
    └── test_projects.py
```

**命名规范：**
- 文件名：snake_case
- 类名：PascalCase
- 模块层级：api（路由）→ services（业务编排）→ engines（纯算法）→ db（数据访问）
- API 路由文件与 URL 前缀对应：`api/projects.py` → `/api/projects`
- 每个路由文件定义自己的 `router = APIRouter()`

**分层规则：**
- `api/` 层不包含业务逻辑，仅做请求解析、响应组装、调用 service
- `services/` 层协调多个 engine 和 db 操作，管理事务
- `engines/` 层是纯业务算法，不依赖 FastAPI、不直接操作数据库
- `db/` 层封装 SQL 操作，返回 dict 或 Pydantic model
- `models/` 层定义数据模型，被所有层共享

---

## 前端目录规范

Phase 0 确立以下目录结构，后续 Phase **禁止自行调整**：

```
frontend/
├── src/
│   ├── main.tsx                # React 入口
│   ├── App.tsx                 # 根组件（路由配置）
│   ├── app/                    # 页面级组件（每个路由一个文件）
│   │   ├── home-page.tsx       # 首页
│   │   ├── project-workbench.tsx  # 项目工作台（Phase 1+ 填充）
│   │   └── rule-management.tsx    # 规则管理（Phase 2 填充）
│   ├── components/             # 可复用 UI 组件
│   │   ├── ui/                 # 基础 UI 组件（按钮、对话框、输入框等）
│   │   ├── project-list.tsx    # 项目列表
│   │   ├── create-project-dialog.tsx
│   │   └── stages/             # 工作台各阶段组件（Phase 1+ 填充）
│   │       └── .gitkeep
│   ├── lib/                    # 工具库
│   │   ├── api.ts              # Axios 实例 + API 调用封装
│   │   └── utils.ts            # 通用工具函数
│   ├── stores/                 # Zustand stores
│   │   └── project-store.ts    # Phase 0 仅定义最小接口
│   ├── types/                  # TypeScript 类型定义
│   │   ├── project.ts          # 项目相关类型
│   │   └── api.ts              # API 响应通用类型
│   └── styles/                 # 全局样式
│       └── globals.css         # Tailwind 入口
├── src-tauri/                  # Tauri Rust 配置
│   ├── tauri.conf.json
│   ├── Cargo.toml
│   ├── src/
│   │   └── main.rs             # Phase 0 仅默认 Tauri 入口，Phase 5 填充 sidecar 管理
│   └── binaries/               # sidecar 二进制（Phase 5 打包时放入）
│       └── .gitkeep
├── index.html
├── vite.config.ts
├── tsconfig.json               # strict: true
├── eslint.config.js
├── tailwind.config.ts
├── package.json
└── pnpm-lock.yaml              # 必须提交
```

**命名规范：**
- 文件名：kebab-case（如 `home-page.tsx`、`project-list.tsx`）
- 组件名：PascalCase（如 `HomePage`、`ProjectList`）
- Store 文件：`xxx-store.ts`，hook 名 `useXxxStore`
- 类型文件：与组件/模块同名，放 `types/` 目录
- 页面组件放 `app/`，可复用组件放 `components/`
- 各阶段组件放 `components/stages/`（Phase 1+ 逐步填充）

**路由模式：**
- 使用 `HashRouter`（不使用 `BrowserRouter`）
- 原因：Tauri 打包后 WebView 加载本地文件，`BrowserRouter` 对刷新和深链接处理不可靠；`HashRouter` 在桌面壳中更稳定
- 此决策在 Phase 0 确定后**不再变更**

**路由结构：**
```
#/                  → HomePage（首页）
#/project/:id       → ProjectWorkbench（项目工作台）
#/rules             → RuleManagement（规则管理）
```

**样式规范：**
- 使用 Tailwind CSS utility class，不写自定义 CSS（除非 Tailwind 无法覆盖）
- 不使用 CSS Modules 或 styled-components
- 颜色/间距使用 Tailwind 的 design token

**开发模式下的 API 连通：**
- 使用 Vite 的 proxy 配置将 `/api` 代理到 `http://127.0.0.1:17396`
- 不在后端添加 CORS 中间件
- Token 通过环境变量 `VITE_DEV_TOKEN` 注入（开发模式）

---

## 工程门禁配置

### 后端 pyproject.toml

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### 后端 requirements-dev.txt

```txt
pytest>=8.0.0
pytest-anyio>=0.0.0
httpx>=0.27.0
anyio>=4.0.0
ruff>=0.8.0
mypy>=1.13.0
```

### 前端 ESLint + TypeScript

- ESLint：使用 `@eslint/js` + `typescript-eslint` 推荐配置
- TypeScript：`strict: true`，`noEmit: true`（类型检查用）
- package.json scripts：
  ```json
  {
    "scripts": {
      "dev": "vite",
      "build": "tsc && vite build",
      "lint": "eslint src/",
      "tsc": "tsc --noEmit",
      "preview": "vite preview"
    }
  }
  ```

---

## 任务列表与依赖关系

```
      ┌─── 0.1 后端骨架 ──┬── 0.2 认证中间件 ──┐
      │                   │                    │
      │                   └── 0.3 数据库层 ─────┤
      │                                        │
      │                                   0.4 项目 CRUD API ── 0.5 openapi
      │                                        │
      └─── 0.6 前端骨架 ── 0.7 API Client ─────┤
                                               │
                                          0.8 首页连通
```

**并行化：**
- 0.1（后端骨架）与 0.6（前端骨架）完全并行
- 0.2 + 0.3 可并行（都仅依赖 0.1）
- 0.7 仅依赖 0.6，可与后端任务并行
- 0.8 等待 0.4 和 0.7 都完成

---

## 完成标准（机器可判定）

### 后端验收

```bash
cd backend

# 1. 工程门禁全部通过
ruff check .                          # exit 0，零警告
mypy . --ignore-missing-imports       # exit 0，零错误
pytest -x -q                          # exit 0，全部通过

# 2. 服务可启动
# 启动后端（开发模式，跳过 token 校验）
DEV_MODE=1 uvicorn main:app --host 127.0.0.1 --port 17396 &
sleep 2

# 3. health API
curl -sf http://127.0.0.1:17396/api/health | python -c "
import sys, json
data = json.load(sys.stdin)
assert data['status'] == 'ok', f'Expected ok, got {data}'
print('✓ health OK')
"

# 4. 项目 CRUD（开发模式无需 token）
# 创建项目
PROJECT=$(curl -sf -X POST http://127.0.0.1:17396/api/projects \
  -H 'Content-Type: application/json' \
  -d '{"name": "测试项目"}')
PROJECT_ID=$(echo $PROJECT | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "✓ 创建项目: $PROJECT_ID"

# 列表查询
curl -sf http://127.0.0.1:17396/api/projects | python -c "
import sys, json
data = json.load(sys.stdin)
assert len(data) >= 1, 'Expected at least 1 project'
print(f'✓ 项目列表: {len(data)} 个')
"

# 详情查询
curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID | python -c "
import sys, json
data = json.load(sys.stdin)
assert data['name'] == '测试项目'
assert 'import_status' in data or 'stage_statuses' in data
print('✓ 项目详情 OK')
"

# 删除项目
curl -sf -X DELETE http://127.0.0.1:17396/api/projects/$PROJECT_ID
echo "✓ 删除项目 OK"

# 5. Token 认证（非开发模式）
kill %1
SESSION_TOKEN=test-token-123 uvicorn main:app --host 127.0.0.1 --port 17396 &
sleep 2

# 无 token → 403
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:17396/api/projects)
[ "$HTTP_CODE" = "403" ] && echo "✓ 无 token → 403" || echo "✗ 预期 403，得到 $HTTP_CODE"

# 有 token → 200
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer test-token-123" \
  http://127.0.0.1:17396/api/projects)
[ "$HTTP_CODE" = "200" ] && echo "✓ 有 token → 200" || echo "✗ 预期 200，得到 $HTTP_CODE"

# health 不需要 token
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:17396/api/health)
[ "$HTTP_CODE" = "200" ] && echo "✓ health 无需 token" || echo "✗ 预期 200，得到 $HTTP_CODE"

kill %1
```

### 前端验收

```bash
cd frontend

# 1. 工程门禁全部通过
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0

# 2. 开发服务器可启动
pnpm dev &
sleep 3

# 3. 页面可访问（手动验证）
# - 首页显示"新建项目"按钮和空项目列表
# - 点击"新建项目" → 弹出对话框 → 输入名称 → 创建成功 → 列表刷新
# - 点击项目 → 跳转到 /project/:id（工作台占位页面）
# - 导航到 /rules → 规则管理占位页面

kill %1
```

### 契约验收

```bash
# openapi.json 已生成且内容正确
test -f docs/api/openapi.json
python -c "
import json
with open('docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())
assert '/api/health' in paths, 'Missing /api/health'
assert '/api/projects' in paths, 'Missing /api/projects'
print(f'✓ openapi.json: {len(paths)} 个路径')
"
```

---

## 数据库 Schema 说明

Phase 0 一次性建好**完整 schema**（所有表），但本 Phase 仅使用 `projects` 和 `schema_version` 表。其余表在后续 Phase 使用时才会有数据写入。

**理由：** 一次建表避免后续 Phase 需要改 schema.sql 和处理迁移。表结构来源于技术架构 3.2 节，已经过多轮评审，稳定。

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-0.1-backend-skeleton.md`
- `task-0.2-auth-middleware.md`
- `task-0.3-database-layer.md`
- `task-0.4-project-crud-api.md`
- `task-0.5-openapi-script.md`
- `task-0.6-frontend-skeleton.md`
- `task-0.7-api-client.md`
- `task-0.8-homepage-integration.md`
