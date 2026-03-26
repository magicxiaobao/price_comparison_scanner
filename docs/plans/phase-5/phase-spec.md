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

| 文件 | 说明 |
|------|------|
| `frontend/src-tauri/src/main.rs` | 填充 sidecar 管理逻辑（Phase 0 仅为默认 Tauri 入口） |
| `frontend/src/components/stage-navigation.tsx` | 阶段状态导航组件 |
| `backend/api/shutdown.py` | `POST /api/shutdown` 优雅关闭路由 |

### 修改

| 文件 | 修改范围 |
|------|----------|
| `backend/main.py` | 注册 shutdown 路由 |
| `frontend/src/app/project-workbench.tsx` | 集成阶段导航组件 |
| `frontend/src-tauri/tauri.conf.json` | 确认 externalBin、CSP 配置正确 |
| `docs/api/openapi.json` | 新增 shutdown 端点 |

---

## 任务列表与依赖关系

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 5.1 | Tauri Sidecar 集成（启动/监控/重启/端口/token/清理） | frontend-dev | Phase 4 |
| 5.2 | 阶段状态导航 + 失效提示 UI | frontend-dev | Phase 4 |
| 5.3 | OCR 接口占位验证 + 未安装时用户提示 | backend-dev | Phase 4 |
| 5.4 | 端到端联调（5 套验收数据集） | reviewer | 5.1, 5.2, 5.3 |
| 5.5 | 生产打包（PyInstaller + Tauri bundler） | frontend-dev + backend-dev | 5.4 |
| 5.6 | 安装包验证 + 最终验收 | reviewer | 5.5 |

```
      ┌── 5.1 Sidecar 集成 ──────┐
      │                           │
      ├── 5.2 阶段导航 UI ────────┤
      │                           ├── 5.4 端到端联调 ── 5.5 生产打包 ── 5.6 最终验收
      └── 5.3 OCR 占位验证 ───────┘
```

**并行化：**
- 5.1（Sidecar 集成）、5.2（阶段导航 UI）、5.3（OCR 占位验证）三者完全并行
- 5.4 等待 5.1 + 5.2 + 5.3 全部完成
- 5.5 等待 5.4 完成
- 5.6 等待 5.5 完成

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

- sidecar 可正常启动并响应 health API
- 心跳检测正常工作
- sidecar 崩溃后自动重启
- 连续崩溃进入安全模式
- 正常退出时进程清理完成
- 异常退出后下次启动能清理孤儿进程

### 打包验收

- PyInstaller 产物可独立运行
- Tauri 安装包可正常安装
- 安装后应用可启动并完成基础流程
- 安装包体积在合理范围（核心包 200-300 MB）

### 性能验收（PRD 9.4）

- Excel 解析 < 3 秒
- Word 解析 < 3 秒
- 数字版 PDF 解析 < 5 秒
- 500 行数据比价+导出可完成（无超时/崩溃）

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-5.1-tauri-sidecar.md`
- `task-5.2-stage-navigation.md`
- `task-5.3-ocr-placeholder.md`
- `task-5.4-e2e-testing.md`
- `task-5.5-production-build.md`
- `task-5.6-final-acceptance.md`
