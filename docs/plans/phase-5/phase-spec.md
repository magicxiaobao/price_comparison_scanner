# Phase 5：集成联调 + 打包 + 验收 — Phase Spec

> **文档优先级：** 本 phase-spec 及其下属 task-spec 的内容优先于 master-plan。若 master-plan 中有与本文档冲突的描述，以本文档为准。

## 目标

完成 Tauri sidecar 全生命周期管理（启动/心跳/重启/安全模式/退出清理），实现阶段状态导航 UI，验证 OCR 接口占位路径，使用 5 套标准验收数据集完成端到端联调，完成生产打包并验证安装包可正常运行。

**本 Phase 是 MVP 的最后一个阶段。** Phase 0-4 已完成全部业务功能，Phase 5 将所有功能集成为可交付的桌面安装包。

## 边界

### 本 Phase 包含

- Tauri Rust 端 sidecar 管理逻辑（`main.rs` 填充：孤儿进程清理、端口扫描、token 生成、sidecar 启动、健康检查、自动重启、安全模式、退出清理）
- 后端 `POST /api/shutdown` 优雅关闭 API
- 阶段状态导航 UI（5 阶段 Tab：pending/completed/dirty/skipped 状态展示 + 失效提示）
- OCR 接口占位验证（确认 `_is_ocr_available()` 返回 False、`_fallback_ocr()` 返回提示、扫描 PDF 上传时用户提示）
- 5 套验收数据集端到端联调（DS-1 ~ DS-5）
- 生产打包（PyInstaller 打包 Python sidecar + Tauri bundler 打包桌面安装包）
- 安装包验证 + MVP 最终验收

### 本 Phase 不包含（明确排除）

- OCR 实际集成（PaddleOCR / PaddlePaddle 集成移到后续版本）
- 自动更新机制
- 系统托盘功能
- 多语言国际化
- 用户手册 / 帮助文档
- CI/CD 流水线搭建
- 跨平台交叉编译（各平台在对应环境上编译）

---

## 本 Phase 引入的新模块 / 修改

### 新增

| 文件 | 说明 | Task |
|------|------|------|
| `frontend/src-tauri/src/main.rs` | 填充 sidecar 管理逻辑（Phase 0 仅为默认 Tauri 入口） | 5.1a / 5.1b |
| `backend/api/shutdown.py` | `POST /api/shutdown` 优雅关闭路由 | 5.1a |
| `backend/tests/test_shutdown.py` | shutdown API 回归测试 | 5.1a |
| `backend/tests/test_ocr_placeholder.py` | OCR 占位路径测试 | 5.3 |
| `scripts/build.sh` | 一键打包脚本 | 5.5 |

### 修改

| 文件 | 修改范围 | Task |
|------|----------|------|
| `frontend/src-tauri/src/lib.rs` | sidecar 启动/管理逻辑（如在此文件中） | 5.1a / 5.1b |
| `frontend/src/main.tsx` | 渲染前调用 `initApiConnection()` 接入启动链路 | 5.1a |
| `frontend/src/lib/api.ts` | 新增 `initApiConnection()` + Tauri invoke 适配 | 5.1a |
| `backend/main.py` | 注册 shutdown 路由 | 5.1a |
| `frontend/src-tauri/tauri.conf.json` | 确认 externalBin、CSP 配置正确 | 5.1a |
| `docs/api/openapi.json` | 新增 shutdown 端点 | 5.1a |
| `backend/engines/document_parser.py` | 确认 OCR 占位逻辑，补充提示消息 | 5.3 |
| `frontend/src/components/stages/import-stage.tsx` | OCR 未安装提示 UI | 5.3 |

### 已完成（Phase 4 提前实现）

| 文件 | 说明 |
|------|------|
| `frontend/src/components/workbench/stage-navigation.tsx` | 阶段状态导航组件（5.2 已完成） |
| `frontend/src/components/workbench/stage-dirty-banner.tsx` | 失效提示横幅（5.2 已完成） |
| `frontend/src/app/project-workbench.tsx` | 已集成阶段导航（5.2 已完成） |

---

## 任务列表与依赖关系

> **拆分说明（2026-03-28）：** 原 Task 5.1 拆分为 5.1a（MVP）和 5.1b（Hardening）两层。5.1a 是 Phase 5 基座，5.1b 视稳定性反馈决定是否前置。Task 5.2（阶段导航 UI）已在 Phase 4 中提前完成。
>
> **工作流定性：** Phase 5 采用「基座先行 + 条件加固 + 串行验收」工作流。不使用 contract-first 作为主流程（Phase 5 瓶颈在进程生命周期、平台环境和打包链路，不在接口契约）。仅在 5.1a 的 `POST /api/shutdown` 和 `get_sidecar_info` 上做轻量局部契约先行。

| Task | 名称 | 负责人 | 依赖 | 状态 |
|------|------|--------|------|------|
| 5.1a | Sidecar MVP（启动/端口/token/退出清理/前端初始化） | frontend-owner + backend-dev | Phase 4 | 待实现 |
| 5.1b | Sidecar 加固（心跳/重启/安全模式/孤儿清理） | frontend-owner | 5.1a | **必须实施，仅排期条件化**（视 G1 后决定前置或后置） |
| 5.2 | 阶段状态导航 + 失效提示 UI | — | Phase 4 | **已完成**（Phase 4 提前实现） |
| 5.3 | OCR 接口占位验证 + 未安装时用户提示 | ocr-worker | Phase 4 | 部分完成，需补测试 + 前端提示 |
| 5.4 | 端到端联调（5 套验收数据集） | reviewer + leader | 5.1a, 5.3 | 待实现 |
| 5.5 | 生产打包（PyInstaller + Tauri bundler） | backend-dev + frontend-owner | 5.4 | 待实现 |
| 5.6 | 安装包验证 + 最终验收 | reviewer + leader | 5.5 | 待实现 |

---

## 执行编排：基座先行 + 条件加固 + 串行验收

### W0 基线确认（Leader + Reviewer）

确认以下前提条件：
- 5.2 已完成，从执行路径剔除
- 5.1a 为当前首要执行依据
- 5.1b 为条件任务，不默认进入 W1
- 5.3 与 5.1a 可并行

### W1 并行（基座 + OCR 收口）

**frontend-owner**（Rust/Tauri 侧）：5.1a 的 Tauri 集成
- `frontend/src-tauri/src/main.rs` + `lib.rs` — sidecar 启动/退出/invoke
- `frontend/src/main.tsx` — 启动初始化接线
- `frontend/src/lib/api.ts` — `initApiConnection()` + Tauri 模式适配

**backend-dev**（Python 侧）：5.1a 的 shutdown API
- `backend/api/shutdown.py` — 优雅关闭路由
- `backend/main.py` — 注册路由
- `backend/tests/test_shutdown.py` — 回归测试
- `docs/api/openapi.json` — 契约更新

**ocr-worker**：5.3 OCR 占位补完
- `backend/engines/document_parser.py` — 确认 OCR 占位逻辑
- `backend/tests/test_ocr_placeholder.py` — 新建测试
- `frontend/src/components/stages/import-stage.tsx` — OCR 未安装提示 UI

### G1 门禁审查（Reviewer）

放行条件：
- 5.1a 门禁全部通过（后端 `ruff + mypy + pytest`，前端 `lint + tsc`）
- sidecar MVP 手工验证通过（启动 → 连接 → API 调用 → 退出清理）
- 5.3 占位路径测试通过 + 前端提示 UI 可用
- reviewer 必须贴完整门禁命令原始输出

### W2 稳定性决策（Leader + Reviewer）

判断是否在 5.4 之前插入 5.1b。

**插入 5.1b 的条件**（任一命中即插入）：
- `pnpm tauri dev` 下 sidecar 启动不稳（偶发超时）
- 退出后残留进程
- 端口占用恢复差
- sidecar 偶发失联导致前端 API 报错

**不前置 5.1b 的条件**：
- 5.1a 已足够稳定支撑 E2E 全流程
- 此时 5.1b 后置到 W4 之后（W4.5），仍须在 Phase 5 关闭前完成

> **W2 决策记录（2026-03-28）：不前置 5.1b，先进入 5.4。**
> - 依据：sidecar 二进制（PyInstaller 产物）尚未就绪，`pnpm tauri dev` 无法产生有效稳定性结论。5.1a 代码已过 G1 门禁（6/6 全绿 + reviewer 代码审查通过）。
> - 5.4 E2E 使用 `uvicorn + pnpm dev` 开发模式执行，不依赖 Tauri sidecar。
> - 若 5.4 过程中暴露 sidecar 相关不稳定（启动不稳、退出残留、失联、端口恢复差），则在 W4 之后插入 W4.5 = 5.1b，并重跑受影响的 E2E 用例。
> - **不前置 ≠ 取消**：5.1b 仍是 Phase 5 必须交付项，必须在 W5 打包前完成。

> **口径澄清：** 5.1b 是 Phase 5 的必须交付项（顶层目标包含心跳/重启/安全模式/孤儿清理），不是可选增强。W2 决策的是"前置还是后置"，不是"做还是不做"。若 W2 决定不前置，5.1b 在 W4 之后、W5 之前作为 W4.5 执行。

### W3 条件波次（W2 决策为"前置"时执行）

**frontend-owner**：5.1b Sidecar 加固
- 心跳循环、自动重启、安全模式、孤儿进程清理
- 前端事件监听（`sidecar-restarted` / `sidecar-safe-mode`）

### W4.5 后置收口（W2 决策为"不前置"时，在 W4 完成后执行）

**frontend-owner**：5.1b Sidecar 加固（同 W3 内容）
- 此时 E2E 已验证基础稳定性，加固工作风险更低
- 完成后由 reviewer 补充 5.1b 验收项，确认后再进入 W5

### W4 端到端联调

**reviewer**（主负责人）+ **leader**（协调）：5.4 E2E
- Agent 准备：测试数据文件、验收脚本、检查表、结果模板
- Agent 执行：dev 模式下可自动化的流程验证、日志收集
- 人工确认：桌面端真实体验、UI/交互感受、最终结论

### G2 联调门禁（Reviewer）

放行条件：
- DS-1 ~ DS-5 验证清单全部通过
- 质量指标达标（映射命中率 ≥ 80%、归组无修改率 ≥ 90%、异常检出 100%、追溯完整 100%）
- 性能指标达标
- 综合验收报告已生成

### W5 生产打包

**backend-dev**：PyInstaller 打包 + sidecar 可执行文件自验证
**frontend-owner**：Tauri bundler + `scripts/build.sh` + `tauri.conf.json` 确认

### G3 打包门禁（Reviewer）

放行条件：
- sidecar 二进制可独立启动并响应 health API
- Tauri 安装包产出成功（.dmg / .msi / .AppImage）
- 安装包体积在合理范围（200-300 MB）
- 产物路径和命名符合 spec

### W6 最终验收

**reviewer**（主负责人）+ **leader**（协调）：5.6
- 安装包环境下完整流程验证
- 46 项 PRD 第 10 节验收清单
- 最终发布判定（PASS / CONDITIONAL PASS / FAIL）

> W6 期间不并行其他功能任务，确保验收环境干净。

---

### 角色分配

| 角色 | 职责范围 |
|------|----------|
| **leader** | 波次推进、5.1b 插入决策、最终发布口径协调 |
| **frontend-owner** | Tauri/Rust 整合、前端启动接线、5.5 Tauri 打包链路 |
| **backend-dev** | shutdown API、测试、PyInstaller 打包、sidecar 自验证 |
| **ocr-worker** | 5.3 OCR 占位补完（Phase 5 最适合并行切出的小任务） |
| **reviewer** | G1/G2/G3 门禁、5.4/5.6 主验收口径 |

### 并行性约束

**适合并行：**
- 5.1a 的 Rust/Tauri 侧 与 Python shutdown 侧
- 5.1a 与 5.3
- 5.5 中 backend packaging 与 frontend bundling 准备

**不适合并行：**
- 5.4 / 5.5 / 5.6 必须严格串行
- 5.1b 与 5.4 不应同时推进
- W6 最终验收期间不混入功能开发

```
W0 基线确认
 │
W1 ┌── 5.1a (frontend-owner + backend-dev) ──┐
   └── 5.3 (ocr-worker) ────────────────────┘
 │
G1 reviewer 门禁
 │
W2 稳定性决策 ── 前置 5.1b? ──┐
 │                              │ 是
W3 5.1b (frontend-owner)  ◄────┘
 │                              │ 否（后置）
W4 5.4 E2E (reviewer + leader) ◄┘
 │
G2 联调门禁
 │
W4.5 5.1b 后置收口 ◄── 仅当 W2 决策为"不前置"时执行
 │
W5 5.5 打包 (backend-dev + frontend-owner)
 │
G3 打包门禁
 │
W6 5.6 最终验收 (reviewer + leader)

注：无论走 W3 还是 W4.5，5.1b 都在 W5 之前完成
```

---

## 完成标准（按 PRD 第 10 节验收标准）

### 10.1 基础流程验收

```
新建项目 → 导入 3 家供应商文件 → 确认供应商名称 → 选择表格
→ 应用规则标准化 → 手工修正 → 确认归组 → 生成比价 → 导出 Excel
```

- 以 DS-1 数据集跑通完整流程
- 导出的 Excel 包含 3 个 Sheet（比价汇总、明细数据、追溯信息）

### 10.2 规则管理验收

- 规则 CRUD 可用
- 规则导入/导出可用
- 内置模板可加载
- 项目中新增映射可保存为全局规则

### 10.3 追溯能力验收

导出 Excel 中可查看：
- 来源文件 + 供应商
- 表格来源（sheet 名/页码）
- 原始字段与标准字段关系
- 命中规则
- 手工修改记录
- 低置信标记

### 10.4 异常控制验收

以 DS-3 数据集验证，系统必须检出：
- 税价口径不一致
- 单位不一致
- 币种不一致
- 商品未确认归组
- 低置信字段未确认
- 预设 8 个异常全部检出（100%）

### 10.5 质量指标验收

- 追溯完整率：100%（导出 Excel 中每行可追溯到来源）
- 字段自动映射命中率：≥ 80%（DS-1、DS-2）
- 高置信归组无需修改率：≥ 90%（DS-4）
- 异常检出率：100%（DS-3）

### Sidecar 验收

**5.1a-MVP（必须通过）：**
- sidecar 可正常启动并响应 health API
- 端口冲突时自动使用下一个可用端口
- 前端通过 invoke 获取 port/token 并正常调用后端 API
- 正常退出时进程清理完成 + PID 文件删除

**5.1b-Hardening（视实施情况验收）：**
- 心跳检测正常工作
- sidecar 崩溃后自动重启
- 连续崩溃进入安全模式
- 异常退出后下次启动能清理孤儿进程

### 打包验收

- PyInstaller 产物可独立运行
- Tauri 安装包可正常安装
- 安装后应用可启动并完成基础流程
- 安装包体积在合理范围（核心包 200-300 MB）

### 性能验收（PRD 9.4）

- Excel 解析 < 3 秒（DS-2 实际文件）
- Word 解析 < 3 秒（DS-2 实际文件）
- 数字版 PDF 解析 < 5 秒（DS-2 实际文件）
- 500 行合成数据比价+导出可完成（无超时/崩溃，Task 5.6 生成合成数据验证）

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-5.1-tauri-sidecar.md`（原始全量 spec，保留供参考）
- `task-5.1a-sidecar-mvp.md`（**执行依据** — MVP 层）
- `task-5.1b-sidecar-hardening.md`（**执行依据** — 加固层）
- `task-5.2-stage-navigation.md`（已完成）
- `task-5.3-ocr-placeholder.md`
- `task-5.4-e2e-testing.md`
- `task-5.5-production-build.md`
- `task-5.6-final-acceptance.md`
