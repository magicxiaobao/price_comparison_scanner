# 三方比价支出依据扫描工具 — 技术架构设计

> **文档版本**：v1.4 | **最后更新**：2026-03-26

### 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-03-26 | 初始技术架构文档，确定 Tauri + React + Python Sidecar 混合架构 |
| v1.1 | 2026-03-26 | 整合评审反馈：Sidecar 启动/监控/端口冲突机制、Tauri 配置示例、OCR 置信度与 UI 联动、source_location JSON 示例、API 请求体示例、部署与打包流程、Zustand Store 完整示例 |
| v1.2 | 2026-03-26 | 第二轮评审：Sidecar 安全加固（127.0.0.1 绑定 + session token + 孤儿进程清理）、字段级追溯粒度、引擎版本留痕、TaskManager 抽象层、SQLite 约束与迁移策略、JSON 原子写入、API 命名统一 |
| v1.3 | 2026-03-26 | 终审修正：engine_versions 下沉到归组/比价批次、audit_logs 补 action_source、comparison_status 显式状态、Sidecar 重启端口兜底和安全模式、JSON 读写边界约束、章节编号修正 |
| v1.4 | 2026-03-26 | 新增模块：项目需求标准与供应商符合性匹配（ComplianceEvaluator），新增 requirement_items + compliance_matches 表，比价支持双口径最低价，5 阶段工作台，失效传播链更新，API/页面/Store 同步扩展 |

------

## 1. 架构概述

### 1.1 架构目标

- 完全本地运行，无任何网络依赖
- 高可控 + 可追溯（每一步人工确认、操作留痕）
- 阶段化工作台 + 失效传播机制
- 项目自包含（便于备份、归档、迁移）
- 易扩展（后续支持 OCR 增强、语义归组等）

### 1.2 整体架构（Tauri + Python Sidecar）

```
┌──────────────────────────────────────────────────────────┐
│  Tauri 桌面壳（Rust）                                     │
│  窗口管理、文件对话框、系统托盘、自动更新                   │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  前端 UI（React + TypeScript + Tailwind CSS）       │  │
│  │                                                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │  │
│  │  │ 导入文件  │ │ 标准化   │ │商品归组 │ │符合性审查│ │比价导出│ │  │
│  │  └──────────┘ └──────────┘ └────────┘ └────────┘ └────────┘ │  │
│  │  ┌──────────────────────────────────────────────┐ │  │
│  │  │ 待处理问题清单（跨阶段全局面板）              │ │  │
│  │  └──────────────────────────────────────────────┘ │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │ HTTP JSON API（localhost）        │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │  Python Sidecar（FastAPI）                          │  │
│  │                                                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────┐ │  │
│  │  │DocumentParser│ │ RuleEngine │  │TableStandardizer│ │
│  │  └────────────┘  └────────────┘  └──────────────┘ │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────┐ │  │
│  │  │CommodityGrouper│ │PriceComparator│ │ReportGenerator│ │
│  │  └────────────┘  └────────────┘  └──────────────┘ │  │
│  │                                                    │  │
│  │  SQLite（项目数据） + JSON（全局配置） + 文件系统    │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 1.3 Sidecar 启动与监控机制

#### 启动流程

```
Tauri 应用启动
  → 检查并清理孤儿进程（读取 PID 文件，若存在则 kill）
  → 生成一次性 session token（随机 UUID）
  → 扫描可用端口（默认 17396，冲突时自动递增至 17396-17406）
  → 启动 Python sidecar：backend --host 127.0.0.1 --port <port> --token <token>
  → sidecar 写入 PID 文件（app_data/.sidecar.pid）
  → 等待 sidecar 就绪（轮询 GET /api/health + Authorization header，超时 10 秒）
  → 就绪后前端开始加载，注入 port 和 token
```

#### 网络安全

- sidecar **必须绑定 `127.0.0.1`**，不得绑定 `0.0.0.0`（防止局域网访问）
- 所有 API 请求必须携带 `Authorization: Bearer <session_token>` header
- session token 在每次应用启动时重新生成，sidecar 校验每个请求
- 不符合 token 的请求返回 `403 Forbidden`

#### 端口冲突处理

- 默认端口 `17396`，启动前检测是否被占用
- 若冲突，自动尝试 `17397` ... `17406`（最多 10 次）
- 选定的端口通过 Tauri 的 `invoke` 机制传给前端
- 10 次均冲突则弹窗提示用户关闭占用端口的程序

#### 健康检查与自动重启

- Tauri 每 5 秒向 `GET /api/health` 发送心跳
- 若连续 3 次心跳失败（15 秒无响应），判定 sidecar 崩溃
- 自动重启 sidecar 进程（同一端口、同一 token），重启后前端自动重连
- 若原端口不可用，重新扫描可用端口并通过 Tauri invoke 通知前端更新连接地址
- 重启次数上限 3 次 / 分钟，超过后进入 **安全模式**（只读状态：可查看已有项目数据，但不能执行导入、标准化、归组、比价等写操作），弹窗提示用户
- 项目数据在 SQLite 中安全持久化，sidecar 重启后状态可恢复

#### 进程清理

- **正常退出**：Tauri 主进程关闭时，向 sidecar 发送 `POST /api/shutdown`，等待 3 秒后强制 kill，删除 PID 文件
- **异常退出**（崩溃/强制结束）：下次启动时检查 PID 文件，若进程仍存在则 kill 后再启动新 sidecar
- PID 文件位置：`app_data/.sidecar.pid`

#### Tauri 配置示例

`tauri.conf.json` 中的 sidecar 定义：

```json
{
  "bundle": {
    "externalBin": [
      "binaries/backend"
    ]
  },
  "app": {
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://localhost:17396 http://localhost:17397 http://localhost:17398 http://localhost:17399 http://localhost:17400 http://localhost:17401 http://localhost:17402 http://localhost:17403 http://localhost:17404 http://localhost:17405 http://localhost:17406"
    }
  }
}
```

> **平台说明**：sidecar 可执行文件按平台命名（`backend-x86_64-pc-windows-msvc.exe`、`backend-aarch64-apple-darwin`、`backend-x86_64-unknown-linux-gnu`），Tauri 打包时自动选择对应平台的二进制文件。

### 1.4 架构决策说明

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 桌面框架 | Tauri（非 Electron、非 PySide6） | 体积小（~10MB）、跨平台、前端 UI 交互能力强 |
| 前端 | React + TypeScript | 表格组件生态成熟、类型安全、Tauri 官方支持良好 |
| 后端 | Python Sidecar（FastAPI） | Python 文档解析/OCR 库成熟度远高于其他语言 |
| GUI 不选 PySide6 | — | 产品有大量表格交互（修正、拖拽归组、高亮异常），PySide6 的 QTableView 定制成本高 |
| 前后端通信 | 本地 HTTP JSON API | 简单可靠，FastAPI 自带 OpenAPI 文档，联调方便 |

### 1.5 核心数据流

```
文件上传
  → Tauri 文件对话框选择文件
  → 前端调用 POST /api/projects/{id}/files
  → DocumentParser（分格式解析：xlsx/docx/pdf/ocr）
  → 返回 RawTable 列表

规则应用 & 标准化
  → 前端调用 POST /api/projects/{id}/standardize
  → RuleEngine（全局规则 + 项目覆盖 → 列名映射 + 冲突解决）
  → TableStandardizer（字段标准化 + 总价计算）
  → 返回 StandardizedRow 列表 + 规则命中快照

商品归组
  → 前端调用 POST /api/projects/{id}/grouping/generate
  → CommodityGrouper（归一化 → 多因子打分 → 三档置信度分层）
  → 返回候选归组列表

符合性审查（可选）
  → 用户录入/导入需求标准（可在任何阶段进行）
  → 前端调用 POST /api/projects/{id}/compliance/evaluate
  → ComplianceEvaluator（关键词/数值/人工 三类匹配）
  → 返回符合性矩阵 + 有资格参与有效最低价的供应商列表

比价 & 导出
  → 前端调用 POST /api/projects/{id}/comparison/generate
  → PriceComparator（比价计算 + 异常检测）
  → 前端调用 POST /api/projects/{id}/export
  → ReportGenerator（3 Sheet Excel 导出）
```

------

## 2. 技术栈

### 2.1 前端技术栈

| 组件 | 版本建议 | 许可证 | 用途 |
|------|----------|--------|------|
| Tauri | 2.x | MIT | 桌面壳、窗口管理、sidecar 管理 |
| React | 19+ | MIT | UI 框架 |
| TypeScript | 5.x | Apache 2.0 | 类型安全 |
| Tailwind CSS | 4.x | MIT | 样式 |
| TanStack Table | 8.x | MIT | 表格组件（标准化预览、比价结果） |
| dnd-kit | 6.x | MIT | 拖拽交互（归组调整） |
| Zustand | 5.x | MIT | 状态管理 |
| Axios | 1.x | MIT | HTTP 请求 |

### 2.2 后端技术栈（Python Sidecar）

| 组件 | 版本建议 | 许可证 | 用途 |
|------|----------|--------|------|
| Python | 3.11+ | PSF | 运行时 |
| FastAPI | 0.115+ | MIT | HTTP API 框架 |
| Uvicorn | 0.34+ | BSD | ASGI 服务器 |
| pdfplumber | 0.11+ | MIT | PDF 结构化表格提取（主力） |
| pypdf | 5.x | BSD | PDF 文本提取和元信息读取（辅助） |
| python-docx | 1.1+ | MIT | Word 文档表格提取 |
| openpyxl | 3.1+ | MIT | Excel 读取 + 审计底稿导出 |
| pandas | 2.2+ | BSD | 数据处理、标准化、比价计算 |
| rapidfuzz | 3.15+ | MIT | 模糊匹配（规则引擎 + 归组） |
| loguru | 0.7+ | MIT | 结构化日志 |
| Pillow | 11+ | HPND | 图像预处理（OCR 前置） |
| SQLite3 | 内置 | Public Domain | 项目数据存储 |

### 2.3 OCR 可选模块（独立安装）

| 组件 | 版本建议 | 许可证 | 用途 |
|------|----------|--------|------|
| PaddleOCR | 2.9+ | Apache 2.0 | 表格 OCR 识别 |
| PaddlePaddle | 3.0+ | Apache 2.0 | OCR 运行框架 |
| PP-StructureV3 | — | Apache 2.0 | 表格结构化识别 |

> **安装策略**：OCR 模块不包含在核心安装包中。首次使用 OCR 功能时，系统提示用户安装 OCR 扩展包（离线安装包形式，约 800MB）。安装后完全本地运行，无需联网。
>
> **OCR 结果与 UI 联动**：安装完成后，通过 OCR 解析的文件在文件列表中显示「OCR」徽章，且 OCR 产出的标准化行中 `confidence < 0.9` 的字段默认标记为「需人工复核」（`needs_review = 1`），在待处理问题清单中集中展示。

### 2.4 打包与分发

| 组件 | 用途 |
|------|------|
| Tauri bundler | 前端 + Tauri 壳打包（.msi / .dmg / .AppImage） |
| PyInstaller | Python 后端打包为独立可执行文件（sidecar） |

#### 安装包体积预估

| 包 | 预估体积 | 说明 |
|----|----------|------|
| 核心安装包（不含 OCR） | 200-300 MB | Tauri + React + Python sidecar（含 pandas、pdfplumber 等） |
| OCR 扩展包 | ~800 MB | PaddleOCR + PaddlePaddle + 模型文件 |

------

## 3. 数据存储设计

### 3.1 全局数据（JSON 文件）

位于 `app_data/` 目录，永久保存。

> **原子写入约束**：所有全局 JSON 文件的写操作必须采用原子替换策略：先写入临时文件（`.tmp`）→ `fsync` 刷盘 → `rename` 替换原文件。防止程序崩溃时写坏规则或配置文件。

#### 目录结构

```text
app_data/
  config.json                  # 应用配置、最近项目列表
  rules/
    default-template.json      # 内置默认模板
    it-device-template.json    # IT 设备模板
    user-rules.json            # 用户自定义规则
  projects/
    <project_id>/
      project.db               # 项目 SQLite 数据库
      source_files/             # 原始文件副本
      exports/                  # 导出的 Excel 文件
```

#### 规则 JSON 结构

```json
{
  "version": "1.0",
  "lastUpdated": "2026-03-26T14:30:00",
  "templates": {
    "default": "通用采购模板",
    "it_device": "IT设备模板"
  },
  "columnMappingRules": [
    {
      "id": "rule-001",
      "enabled": true,
      "type": "column_mapping",
      "sourceKeywords": ["价格", "单价", "报价", "Unit Price", "含税单价"],
      "targetField": "unit_price",
      "matchMode": "fuzzy",
      "priority": 100,
      "createdAt": "2026-03-26T10:00:00"
    }
  ],
  "valueNormalizationRules": [
    {
      "id": "rule-val-001",
      "type": "value_normalization",
      "field": "product_name",
      "patterns": ["lenovo", "联想"],
      "replaceWith": "联想",
      "createdAt": "2026-03-26T10:00:00"
    }
  ]
}
```

### 3.2 项目数据（SQLite）

每个项目一个独立的 `project.db` 文件。

#### 标准字段英文映射

| 中文字段名 | 英文列名 | 数据类型 |
|-----------|----------|----------|
| 商品名称 | product_name | TEXT |
| 规格型号 | spec_model | TEXT |
| 单位 | unit | TEXT |
| 数量 | quantity | REAL |
| 单价 | unit_price | REAL |
| 总价 | total_price | REAL |
| 税率 | tax_rate | TEXT |
| 交期 | delivery_period | TEXT |
| 备注 | remark | TEXT |

#### 表结构

```sql
-- ============================================================
-- 项目基本信息（含阶段状态，合并为单表）
-- ============================================================
-- 注意：每次打开项目数据库时必须执行 PRAGMA foreign_keys = ON;
-- 数据库版本通过 schema_version 表管理，支持后续迁移

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'));

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- 引擎版本留痕（每次执行标准化/归组/比价时更新）
    engine_versions TEXT,                         -- JSON: {"rule_set_hash":"abc123","grouping_version":"1.0","normalization_version":"1.0","comparison_version":"1.0"}
    -- 阶段状态
    import_status TEXT DEFAULT 'pending' CHECK(import_status IN ('pending','completed','dirty')),
    import_completed_at TEXT,
    normalize_status TEXT DEFAULT 'pending' CHECK(normalize_status IN ('pending','completed','dirty')),
    normalize_completed_at TEXT,
    grouping_status TEXT DEFAULT 'pending' CHECK(grouping_status IN ('pending','completed','dirty')),
    grouping_completed_at TEXT,
    compliance_status TEXT DEFAULT 'skipped' CHECK(compliance_status IN ('pending','completed','dirty','skipped')),
    compliance_completed_at TEXT,
    comparison_status TEXT DEFAULT 'pending' CHECK(comparison_status IN ('pending','completed','dirty')),
    comparison_completed_at TEXT
);

-- ============================================================
-- 供应商文件
-- ============================================================
CREATE TABLE supplier_files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL,
    supplier_confirmed INTEGER DEFAULT 0,         -- 0=未确认 1=已确认
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,                       -- 相对路径 source_files/xxx
    file_type TEXT NOT NULL CHECK(file_type IN ('xlsx','docx','pdf','image')),
    recognition_mode TEXT CHECK(recognition_mode IN ('structure','ocr','manual')),
    imported_at TEXT NOT NULL
);

-- ============================================================
-- 解析得到的原始表格
-- ============================================================
CREATE TABLE raw_tables (
    id TEXT PRIMARY KEY,
    supplier_file_id TEXT NOT NULL REFERENCES supplier_files(id) ON DELETE CASCADE,
    table_index INTEGER NOT NULL,                  -- 文件内表格序号
    sheet_name TEXT,                                -- Excel sheet 名
    page_number INTEGER,                           -- PDF 页码
    row_count INTEGER,
    column_count INTEGER,
    raw_data TEXT NOT NULL,                         -- JSON 序列化的表格数据（后续高频查询可能拆表）
    selected INTEGER DEFAULT 1                     -- 是否参与比价
);

-- ============================================================
-- 标准化结果（核心表）
-- ============================================================
CREATE TABLE standardized_rows (
    id TEXT PRIMARY KEY,
    raw_table_id TEXT NOT NULL REFERENCES raw_tables(id) ON DELETE CASCADE,
    supplier_file_id TEXT NOT NULL REFERENCES supplier_files(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    -- 标准字段（英文列名）
    product_name TEXT,
    spec_model TEXT,
    unit TEXT,
    quantity REAL,
    unit_price REAL,
    total_price REAL,                                -- 写入前必须校验：若原表未提供则由 TableStandardizer 自动计算 quantity × unit_price
    tax_rate TEXT,
    delivery_period TEXT,
    remark TEXT,
    -- 来源定位（字段级 JSON Map，每个标准字段独立记录来源，示例见下方）
    source_location TEXT NOT NULL,
    -- 规则命中快照
    column_mapping TEXT,                            -- JSON: {"原始列名":"标准字段", ...}
    hit_rule_snapshots TEXT,                        -- JSON: [{"rule_id":"rule-001","rule_name":"单价映射","match_content":"报价→unit_price","match_mode":"fuzzy"}, ...]
    -- 元数据
    confidence REAL DEFAULT 1.0,                    -- 置信度 0-1
    is_manually_modified INTEGER DEFAULT 0,
    needs_review INTEGER DEFAULT 0,                 -- 低置信或异常时标记为需复核
    tax_basis TEXT                                  -- known_inclusive / known_exclusive / unknown
);

-- ============================================================
-- 商品归组
-- ============================================================
CREATE TABLE commodity_groups (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    group_name TEXT,                                -- 归组显示名称
    normalized_key TEXT,                            -- 归一化后的匹配键
    confidence_level TEXT NOT NULL CHECK(confidence_level IN ('high','medium','low')),
    engine_versions TEXT,                           -- JSON: 该批次归组时的引擎版本快照
    match_score REAL,                               -- 多因子综合得分
    match_reason TEXT,                              -- 可读归组理由
    status TEXT DEFAULT 'candidate' CHECK(status IN ('candidate','confirmed','split','not_comparable')),
    confirmed_at TEXT
);

CREATE TABLE group_members (
    group_id TEXT NOT NULL REFERENCES commodity_groups(id) ON DELETE CASCADE,
    standardized_row_id TEXT NOT NULL REFERENCES standardized_rows(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, standardized_row_id)
);

-- ============================================================
-- 比价结果（持久化，避免重复计算）
-- ============================================================
CREATE TABLE comparison_results (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES commodity_groups(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    engine_versions TEXT,                            -- JSON: 该批次比价时的引擎版本快照
    comparison_status TEXT DEFAULT 'comparable' CHECK(comparison_status IN ('comparable','blocked','partial')),
    -- 各供应商报价（JSON 数组，后续如需异常分析可拆为子表）
    supplier_prices TEXT NOT NULL,                   -- JSON: [{"supplier":"联想","unit_price":4299,"total_price":214950}, ...]
    min_price REAL,                                   -- 全量最低价（所有供应商）
    effective_min_price REAL,                         -- 有效最低价（仅符合要求的供应商，无需求标准时等同 min_price）
    max_price REAL,
    avg_price REAL,
    price_diff REAL,                                 -- max - min
    -- 异常标记
    has_anomaly INTEGER DEFAULT 0,
    anomaly_details TEXT,                             -- JSON: [{"type":"tax_basis_mismatch","description":"..."}, ...]（后续如需异常统计可拆为子表）
    -- 缺项
    missing_suppliers TEXT,                           -- JSON: ["供应商C"]
    generated_at TEXT NOT NULL
);

-- ============================================================
-- 操作日志（审计留痕）
-- ============================================================
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    action_type TEXT NOT NULL,                       -- import / standardize / group_confirm / group_split / modify_field / export
    action_source TEXT NOT NULL DEFAULT 'user',      -- user / system / import（区分人工操作与系统自动重算）
    target_table TEXT,                               -- 操作的目标表名
    target_id TEXT,                                  -- 操作的目标记录 ID
    field_name TEXT,                                 -- 修改的具体字段名（如 unit_price）
    before_value TEXT,
    after_value TEXT,
    created_at TEXT NOT NULL
);

-- ============================================================
-- 项目需求标准（可选模块）
-- ============================================================
CREATE TABLE requirement_items (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT,                                       -- 需求编号（如 REQ-001）
    category TEXT,                                   -- 功能要求 / 技术规格 / 商务条款 / 服务要求 / 交付要求
    title TEXT NOT NULL,                             -- 需求标题
    description TEXT,                                -- 需求详细描述
    is_mandatory INTEGER DEFAULT 1,                  -- 1=必选 0=可选
    match_type TEXT NOT NULL CHECK(match_type IN ('keyword','numeric','manual')),
    expected_value TEXT,                              -- 关键词、数值条件或人工说明
    operator TEXT,                                   -- numeric 类型时的比较操作符：gte/lte/eq/range
    sort_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- ============================================================
-- 供应商符合性匹配结果（以 商品组×供应商×需求项 为对象）
-- ============================================================
CREATE TABLE compliance_matches (
    id TEXT PRIMARY KEY,
    requirement_item_id TEXT NOT NULL REFERENCES requirement_items(id) ON DELETE CASCADE,
    commodity_group_id TEXT NOT NULL REFERENCES commodity_groups(id) ON DELETE CASCADE,
    supplier_file_id TEXT NOT NULL REFERENCES supplier_files(id) ON DELETE CASCADE,
    -- 匹配结果
    status TEXT NOT NULL DEFAULT 'unclear' CHECK(status IN ('match','partial','no_match','unclear')),
    is_acceptable INTEGER DEFAULT 0,                 -- 部分符合时，用户是否确认「可接受」
    match_score REAL,                                -- 匹配置信度 0-1
    -- 证据
    evidence_text TEXT,                              -- 从供应商文档中提取的相关原文
    evidence_location TEXT,                          -- JSON: 字段级来源定位（同 source_location 格式）
    match_method TEXT,                               -- keyword / numeric / manual
    -- 人工确认
    needs_review INTEGER DEFAULT 1,
    confirmed_at TEXT,
    engine_versions TEXT                              -- JSON: 该批次匹配时的引擎版本快照
);

-- ============================================================
-- 索引
-- ============================================================
CREATE INDEX idx_requirement_project ON requirement_items(project_id);
CREATE INDEX idx_compliance_requirement ON compliance_matches(requirement_item_id);
CREATE INDEX idx_compliance_group ON compliance_matches(commodity_group_id);
CREATE INDEX idx_compliance_supplier ON compliance_matches(supplier_file_id);
CREATE INDEX idx_std_rows_supplier ON standardized_rows(supplier_file_id);
CREATE INDEX idx_std_rows_table ON standardized_rows(raw_table_id);
CREATE INDEX idx_group_members_group ON group_members(group_id);
CREATE INDEX idx_group_members_row ON group_members(standardized_row_id);
CREATE INDEX idx_comparison_group ON comparison_results(group_id);
CREATE INDEX idx_audit_project ON audit_logs(project_id);
CREATE INDEX idx_audit_target ON audit_logs(target_id);
```

#### `source_location` 字段 JSON 结构示例

`source_location` 采用 **字段级追溯**：JSON Map 的 key 为标准字段名，value 为该字段的原始来源定位。这样每个字段都能独立追溯到具体的原始单元格。

**Excel（.xlsx）示例**：
```json
{
  "product_name": {"type": "xlsx", "sheet": "报价明细", "cell": "A3"},
  "spec_model":   {"type": "xlsx", "sheet": "报价明细", "cell": "B3"},
  "unit":         {"type": "xlsx", "sheet": "报价明细", "cell": "C3"},
  "quantity":     {"type": "xlsx", "sheet": "报价明细", "cell": "D3"},
  "unit_price":   {"type": "xlsx", "sheet": "报价明细", "cell": "E3"},
  "tax_rate":     {"type": "xlsx", "sheet": "报价明细", "cell": "F3"}
}
```

**Word（.docx）示例**：
```json
{
  "product_name": {"type": "docx", "table_index": 0, "row": 2, "col": 0},
  "spec_model":   {"type": "docx", "table_index": 0, "row": 2, "col": 1},
  "unit_price":   {"type": "docx", "table_index": 0, "row": 2, "col": 4}
}
```

**PDF（结构化提取）示例**：
```json
{
  "product_name": {"type": "pdf", "page": 1, "table_index": 0, "row": 5, "col": 0, "extraction_mode": "structure"},
  "unit_price":   {"type": "pdf", "page": 1, "table_index": 0, "row": 5, "col": 3, "extraction_mode": "structure"}
}
```

**PDF / 图片（OCR 提取）示例**：
```json
{
  "product_name": {"type": "pdf_ocr", "page": 2, "table_index": 0, "row": 3, "col": 0, "extraction_mode": "ocr", "ocr_confidence": 0.85},
  "unit_price":   {"type": "pdf_ocr", "page": 2, "table_index": 0, "row": 3, "col": 3, "extraction_mode": "ocr", "ocr_confidence": 0.72}
}
```

> **JSON 读写约束**：所有 JSON 字段（source_location、column_mapping、hit_rule_snapshots、supplier_prices、anomaly_details、engine_versions 等）必须通过统一的序列化/反序列化模块读写，不允许各业务模块直接拼接 JSON 字符串。每类 JSON 字段定义 Pydantic model 作为 schema 约束，确保结构一致性。
>
> **设计说明**：字段级追溯是审计底稿的硬需求。一行标准化结果中，不同字段可能来自不同原始列甚至不同区域（如税率来自备注列或页脚说明），整行级 `source_location` 不够精确。字段级 JSON Map 在 MVP 阶段查询成本可接受（只需读取不需要 SQL 过滤），后续如需字段级统计分析可考虑拆为独立表。

------

## 4. 核心模块设计

### 4.1 模块职责清单

```
ProjectService              — Facade，协调所有引擎，维护阶段状态和失效传播
DocumentParser              — 文件解析（分格式分发：xlsx/docx/pdf/ocr）
RuleEngine                  — 规则加载、匹配、冲突解决、项目覆盖
TableStandardizer           — 字段映射、值标准化、总价计算
CommodityGrouper            — 归一化、多因子打分、候选归组生成
ComplianceEvaluator         — 需求标准管理、供应商符合性匹配（可选模块）
PriceComparator             — 比价计算、异常检测、有效最低价计算
ReportGenerator             — 4 Sheet Excel 导出（含符合性矩阵，无需求标准时 3 Sheet）
AuditLogService             — 操作留痕（所有修改自动记录）
TaskManager                 — 异步任务管理（提交/进度/取消/结果），MVP 用 ThreadPoolExecutor 实现
```

### 4.2 核心类结构（Python）

```python
# ================================================================
# ProjectService — Facade + 阶段状态管理
# ================================================================
class ProjectService:
    """协调所有引擎，维护阶段状态和失效传播"""

    def create_project(name: str) -> Project
    def import_file(project_id: str, file_path: str) -> SupplierFile
    def confirm_supplier(file_id: str, supplier_name: str)
    def run_standardization(project_id: str) -> List[StandardizedRow]
    def generate_grouping(project_id: str) -> List[CommodityGroup]
    def confirm_group(group_id: str)
    def split_group(group_id: str, new_groups: List)
    def generate_comparison(project_id: str) -> List[ComparisonResult]
    def export_report(project_id: str, output_path: str)

    # 失效传播
    def _propagate_dirty(project_id: str, from_stage: str)
    """
    当 from_stage 的数据发生变更时，将后续所有阶段标记为 dirty。
    例如：from_stage='normalize' → grouping_status='dirty', comparison_status='dirty'
    """

# ================================================================
# DocumentParser — 文件解析引擎
# ================================================================
class DocumentParser:
    """根据文件类型自动分发到对应解析器"""

    def parse(file_path: str) -> List[RawTable]
    def _parse_xlsx(file_path: str) -> List[RawTable]       # openpyxl
    def _parse_docx(file_path: str) -> List[RawTable]       # python-docx
    def _parse_pdf(file_path: str) -> List[RawTable]        # pdfplumber（L1）
    def _fallback_ocr(file_path: str) -> List[RawTable]     # PaddleOCR（L2，可选模块）
    def _is_ocr_available() -> bool                          # 检测 OCR 模块是否已安装

# ================================================================
# RuleEngine — 规则引擎
# ================================================================
class RuleEngine:
    """全局规则 + 项目覆盖，含冲突解决"""

    def load_global_rules() -> RuleSet
    def load_project_overrides(project_id: str) -> RuleSet
    def match_column(column_name: str, rules: RuleSet) -> MatchResult
    def resolve_conflict(matches: List[MatchResult]) -> MatchResult
    """
    冲突解决优先级（PRD 3.1.6）：
    1. 项目级 > 全局用户 > 内置模板
    2. 精确 > 正则 > 模糊
    3. 同层级同方式：后创建优先
    4. 仍有歧义：标记为需人工确认
    """
    def test_rule(column_name: str) -> TestResult            # 最小规则测试能力
    def save_project_override(project_id: str, mapping: dict)
    def save_to_global(mapping: dict)

# ================================================================
# CommodityGrouper — 商品归组引擎（C+ 保守策略）
# ================================================================
class CommodityGrouper:
    """归一化 + 多因子打分 + 三档置信度分层"""

    def generate_candidates(rows: List[StandardizedRow]) -> List[CommodityGroup]
    def normalize_product_name(name: str) -> str
    """品牌别名映射、噪音词降权、大小写统一、标点清理"""
    def normalize_spec(spec: str) -> List[str]
    """拆分为 token 列表"""
    def calculate_match_score(row1, row2) -> MatchScore
    """多因子打分：名称相似度（权重最高）+ 型号 token 重合度 + 单位一致性"""
    def _is_auto_group_forbidden(row1, row2) -> bool
    """
    禁止自动归组的硬约束（PRD 3.1.8）：
    1. 单位不一致
    2. 规格型号核心 token 冲突
    3. 品牌不同
    4. 关键字段低置信且未确认
    5. 数量级差异超过 10 倍
    """

# ================================================================
# ComplianceEvaluator — 供应商符合性匹配引擎（可选模块）
# ================================================================
class ComplianceEvaluator:
    """需求标准管理 + 供应商符合性匹配，以「商品组 × 供应商」为匹配对象"""

    def import_requirements(project_id: str, file_path: str) -> List[RequirementItem]
    """从模板 Excel 导入需求标准"""
    def add_requirement(project_id: str, item: RequirementItem) -> RequirementItem
    def update_requirement(item_id: str, updates: dict)
    def delete_requirement(item_id: str)

    def evaluate(project_id: str) -> List[ComplianceMatch]
    """
    对每个「商品组 × 供应商 × 需求项」执行匹配：
    - keyword: 在标准化数据的规格/备注/名称中搜索关键词
    - numeric: 提取数值与目标值比较
    - manual: 直接标记为待人工确认
    高确定性 → 自动给建议结果；中低确定性 → 待人工确认
    """
    def _match_keyword(requirement: RequirementItem, row: StandardizedRow) -> ComplianceMatch
    def _match_numeric(requirement: RequirementItem, row: StandardizedRow) -> ComplianceMatch

    def confirm_match(match_id: str, status: str, is_acceptable: bool)
    """人工确认匹配结果"""

    def get_compliance_matrix(project_id: str) -> ComplianceMatrix
    """返回符合性矩阵（横轴供应商，纵轴需求项）"""

    def get_eligible_suppliers(group_id: str) -> List[str]
    """返回该商品组中有资格参与有效最低价的供应商列表"""

# ================================================================
# PriceComparator — 比价引擎
# ================================================================
class PriceComparator:
    def compare(groups: List[CommodityGroup], compliance: Optional[ComplianceEvaluator]) -> List[ComparisonResult]
    """若有符合性数据，计算有效最低价；否则有效最低价 = 全量最低价"""
    def detect_anomalies(group: CommodityGroup) -> List[Anomaly]
    """
    异常检测（PRD 5.8 异常处理规则总表）：
    - 税价口径不一致 → 阻断该组最低价结论
    - 单位不一致 → 阻断该组价格比较
    - 币种不一致 → 阻断涉及组的价格比较
    - 必填字段缺失 → 标记但不阻断
    """

# ================================================================
# ReportGenerator — Excel 导出
# ================================================================
class ReportGenerator:
    def export_to_excel(project_id: str, output_path: str)
    """
    Sheet 1: 比价结果表（全量最低价 + 有效最低价高亮、异常标记、符合性摘要）
    Sheet 2: 标准化明细表（含人工修改标记）
    Sheet 3: 追溯信息表（来源定位、规则快照、置信度、修改记录）
    Sheet 4: 需求符合性矩阵（若有需求标准；含证据摘要和确认状态）
    """
```

### 4.3 失效传播机制

```
触发时机                              → 失效范围
──────────────────────────────────────────────────────
修改 standardized_rows 的任意字段     → grouping dirty → compliance dirty → comparison dirty
修改 commodity_groups（确认/拆分/合并）→ compliance dirty → comparison dirty
修改/新增/删除 requirement_items      → compliance dirty → comparison dirty
修改 compliance_matches（确认/调整）  → comparison dirty
新增 supplier_file                    → normalize dirty → grouping dirty → compliance dirty → comparison dirty
删除 supplier_file                    → 同上
修改 supplier_file.supplier_name      → normalize dirty → grouping dirty → compliance dirty → comparison dirty
```

**实现方式**：

- `ProjectService._propagate_dirty()` 在每次修改操作后同步调用
- 失效后下游数据 **保留但标记为 stale**（不删除），用户可以看到上次结果但会提示已失效
- 用户触发重算时，先清除 stale 数据再重新生成

### 4.4 错误处理与异常恢复

#### TaskManager 抽象层

耗时操作通过 `TaskManager` 统一管理，API 层和业务层只依赖 TaskManager 接口，不直接使用线程池。

```python
class TaskManager:
    """任务执行器抽象，MVP 内部使用 ThreadPoolExecutor 实现"""

    def submit(self, task_type: str, params: dict) -> str:
        """提交任务，返回 task_id"""

    def get_status(self, task_id: str) -> TaskStatus:
        """获取任务状态：queued / running / completed / failed / cancelled"""

    def get_progress(self, task_id: str) -> float:
        """获取进度 0.0 - 1.0"""

    def cancel(self, task_id: str) -> bool:
        """取消任务"""

    def get_result(self, task_id: str) -> Any:
        """获取已完成任务的结果"""
```

```
前端 UI 线程            ← HTTP Response →     FastAPI 路由层（快速响应）
                                                      │
                                              TaskManager（接口层）
                                                      │
                                              ThreadPoolExecutor（MVP 实现，可替换）
                                                      │
                                              DocumentParser / CommodityGrouper / ...
```

- 耗时操作（文件解析、OCR、归组计算）通过 `TaskManager.submit()` 提交
- 前端通过轮询 `GET /api/tasks/{task_id}/status` 获取进度
- 支持取消长时间运行的任务（如 OCR）

> **扩展说明**：MVP 使用 ThreadPoolExecutor 作为 TaskManager 的执行后端。后续如果 OCR 模块需要迁到独立进程（避免 GIL 问题或内存隔离），只需替换 TaskManager 的实现，API 层和业务层无需改动。

#### SQLite 事务保护

```python
# 所有写操作使用事务
with db.transaction():
    # 标准化结果写入
    db.insert_standardized_rows(rows)
    # 审计日志写入
    db.insert_audit_log(log)
    # 阶段状态更新
    db.update_stage_status(project_id, 'normalize', 'completed')
# 事务提交成功，或全部回滚
```

#### 异常恢复

- 文件解析崩溃：该文件标记为「解析失败」，不影响其他文件，用户可重试或跳过
- SQLite 写入失败：事务回滚，项目数据保持一致状态
- Python sidecar 崩溃：Tauri 检测到进程退出后自动重启，项目数据在 SQLite 中安全持久化

------

## 5. API 设计概要

### 5.1 API 路由结构

```
POST   /api/projects                          # 新建项目
GET    /api/projects                          # 获取最近项目列表
GET    /api/projects/{id}                     # 获取项目详情（含阶段状态）
DELETE /api/projects/{id}                     # 删除项目

POST   /api/projects/{id}/files               # 导入文件
PUT    /api/files/{id}/confirm-supplier       # 确认供应商名称
GET    /api/projects/{id}/tables              # 获取解析出的表格列表
PUT    /api/tables/{id}/toggle-selection      # 选择/取消表格参与比价

POST   /api/projects/{id}/standardize         # 执行标准化
GET    /api/projects/{id}/standardized-rows   # 获取标准化结果
PUT    /api/standardized-rows/{id}            # 手工修正字段值

POST   /api/projects/{id}/grouping/generate   # 生成归组候选
GET    /api/projects/{id}/groups              # 获取归组列表
PUT    /api/groups/{id}/confirm               # 确认归组
PUT    /api/groups/{id}/split                 # 拆分归组
POST   /api/projects/{id}/grouping/merge      # 手工合并归组

POST   /api/projects/{id}/requirements             # 新增需求项
GET    /api/projects/{id}/requirements             # 获取需求标准列表
PUT    /api/requirements/{id}                      # 更新需求项
DELETE /api/requirements/{id}                      # 删除需求项
POST   /api/projects/{id}/requirements/import      # 从模板 Excel 导入需求标准
GET    /api/projects/{id}/requirements/export      # 导出需求标准模板

POST   /api/projects/{id}/compliance/evaluate      # 执行符合性匹配
GET    /api/projects/{id}/compliance/matrix         # 获取符合性矩阵
PUT    /api/compliance/{id}/confirm                 # 确认匹配结果
PUT    /api/compliance/{id}/accept                  # 标记部分符合为「可接受」

POST   /api/projects/{id}/comparison/generate      # 生成比价结果（含有效最低价）
GET    /api/projects/{id}/comparison               # 获取比价结果

POST   /api/projects/{id}/export                   # 导出 Excel
GET    /api/projects/{id}/problems                 # 获取待处理问题清单

GET    /api/rules                             # 获取全局规则
GET    /api/rules/templates                   # 获取可用模板列表
POST   /api/rules/load-template              # 加载指定模板
PUT    /api/rules                             # 更新全局规则（单条新增/编辑）
DELETE /api/rules/{id}                        # 删除规则
PUT    /api/rules/{id}/toggle                 # 启用/停用规则
POST   /api/rules/import                      # 导入规则（JSON 文件）
GET    /api/rules/export                      # 导出规则（JSON 文件下载）
POST   /api/rules/reset-default              # 恢复默认模板
POST   /api/rules/test                        # 测试规则匹配

GET    /api/tasks/{id}/status                 # 查询异步任务进度
DELETE /api/tasks/{id}                        # 取消任务

GET    /api/health                            # 健康检查（sidecar 心跳）
```

### 5.2 关键 API 请求/响应示例

#### 规则测试 `POST /api/rules/test`

```json
// 请求
{
  "columnName": "报价含税",
  "projectId": "proj-001"           // 可选，传入时叠加项目覆盖规则
}

// 响应
{
  "matched": true,
  "targetField": "unit_price",
  "matchedRule": {
    "id": "rule-001",
    "name": "单价映射",
    "matchMode": "fuzzy",
    "priority": 100,
    "source": "global"              // global / project / template
  },
  "conflicts": [                    // 如有冲突，列出所有命中规则
    {
      "id": "rule-003",
      "name": "含税单价映射",
      "matchMode": "exact",
      "priority": 95,
      "source": "template"
    }
  ],
  "resolution": "rule-001 优先（fuzzy vs exact 同层级，rule-001 优先级更高）"
}
```

#### 手工修正字段 `PUT /api/standardized-rows/{id}`

```json
// 请求
{
  "field": "unit_price",
  "newValue": 4299.00
}

// 响应
{
  "success": true,
  "auditLog": {
    "field": "unit_price",
    "beforeValue": "4300.00",
    "afterValue": "4299.00",
    "timestamp": "2026-03-26T15:30:00"
  },
  "dirtyStages": ["grouping", "comparison"]    // 被标记为失效的下游阶段
}
```

#### 规则导入 `POST /api/rules/import`

```json
// 请求：multipart/form-data，上传 JSON 文件
// 响应
{
  "summary": {
    "total": 15,
    "added": 8,
    "conflicts": 5,
    "skipped": 2
  },
  "conflicts": [
    {
      "importedRule": {"id": "rule-ext-01", "sourceKeywords": ["报价"], "targetField": "unit_price"},
      "localRule": {"id": "rule-001", "sourceKeywords": ["报价", "单价"], "targetField": "unit_price"},
      "status": "pending"           // pending / overwritten / skipped
    }
  ]
}
```

### 5.3 异步任务说明

以下 API 为异步执行，立即返回 `task_id`，前端轮询进度：

- `POST /api/projects/{id}/files`（文件解析，尤其是 PDF/OCR）
- `POST /api/projects/{id}/standardize`（大量行时）
- `POST /api/projects/{id}/grouping/generate`（大量行时）
- `POST /api/projects/{id}/compliance/evaluate`（需求项多、供应商多时）
- `POST /api/projects/{id}/export`（Excel 生成）

------

## 6. 前端架构概要

### 6.1 页面结构

```
App
├── HomePage                           # 首页：新建项目、最近项目、规则管理入口
├── ProjectWorkbench                   # 项目工作台
│   ├── ProblemPanel                   # 待处理问题清单（顶部/侧边常驻）
│   ├── StageNavigation                # 阶段导航栏（含状态指示）
│   ├── ImportStage                    # 第一步：导入文件
│   │   ├── FileUploader
│   │   ├── SupplierConfirmDialog
│   │   └── TableSelector
│   ├── StandardizeStage               # 第二步：标准化
│   │   ├── ColumnMappingPanel
│   │   └── StandardizedDataTable      # 可编辑表格（TanStack Table）
│   ├── GroupingStage                  # 第三步：商品归组
│   │   ├── GroupCandidateList
│   │   └── GroupDragZone              # 拖拽归组（dnd-kit）
│   ├── ComplianceStage                # 第四步：符合性审查（可选）
│   │   ├── RequirementEditor          # 需求标准录入/编辑
│   │   ├── RequirementImporter        # 模板 Excel 导入
│   │   ├── ComplianceMatrix           # 符合性矩阵（横轴供应商 × 纵轴需求项）
│   │   └── EvidenceDetailPanel        # 证据详情面板
│   └── ComparisonStage                # 第五步：比价与导出
│       ├── ComparisonTable
│       ├── AnomalyHighlight
│       └── ExportButton
└── RuleManagement                     # 规则管理窗口
    ├── RuleList
    ├── RuleEditor
    ├── RuleTestPanel                  # 最小规则测试
    └── ImportExportPanel
```

### 6.2 状态管理

使用 Zustand 管理全局状态：

```typescript
// ============================================================
// 项目 Store
// ============================================================
interface ProjectStore {
  currentProject: Project | null;
  stageStatuses: StageStatuses;
  problems: Problem[];
  isLoading: boolean;

  // actions
  loadProject: (id: string) => Promise<void>;
  refreshProblems: () => Promise<void>;
  refreshStageStatuses: () => Promise<void>;
  clearProject: () => void;
}

const useProjectStore = create<ProjectStore>((set, get) => ({
  currentProject: null,
  stageStatuses: { import: 'pending', normalize: 'pending', grouping: 'pending', compliance: 'skipped', comparison: 'pending' },
  problems: [],
  isLoading: false,

  loadProject: async (id) => {
    set({ isLoading: true });
    const project = await api.getProject(id);
    set({ currentProject: project, stageStatuses: project.stageStatuses, isLoading: false });
    get().refreshProblems();
  },

  refreshProblems: async () => {
    const id = get().currentProject?.id;
    if (!id) return;
    const problems = await api.getProblems(id);
    set({ problems });
  },

  refreshStageStatuses: async () => {
    const id = get().currentProject?.id;
    if (!id) return;
    const project = await api.getProject(id);
    set({ stageStatuses: project.stageStatuses });
  },

  clearProject: () => set({ currentProject: null, problems: [], stageStatuses: { import: 'pending', normalize: 'pending', grouping: 'pending', compliance: 'skipped', comparison: 'pending' } }),
}));

// ============================================================
// 规则 Store
// ============================================================
interface RuleStore {
  rules: Rule[];
  templates: Template[];

  loadRules: () => Promise<void>;
  testRule: (columnName: string, projectId?: string) => Promise<TestResult>;
  importRules: (file: File) => Promise<ImportResult>;
  exportRules: () => Promise<Blob>;
}
```

------

## 7. 部署与打包流程

### 7.1 开发环境启动

#### 前提条件

- Node.js 20+、pnpm 9+
- Python 3.11+、pip / uv
- Rust 1.77+（Tauri 编译需要）

#### 启动命令

```bash
# 1. 安装前端依赖
cd frontend
pnpm install

# 2. 安装 Python 后端依赖
cd backend
pip install -r requirements.txt   # 或 uv pip install -r requirements.txt

# 3. 单独启动 Python 后端（开发调试用）
cd backend
uvicorn main:app --port 17396 --reload

# 4. 单独启动前端（开发调试用，连接本地后端）
cd frontend
pnpm dev

# 5. 完整启动（Tauri 开发模式，自动拉起 sidecar）
cd frontend
pnpm tauri dev
```

### 7.2 生产打包

#### Python 后端打包为 Sidecar

```bash
cd backend

# Windows
pyinstaller --onefile --name backend-x86_64-pc-windows-msvc main.py

# macOS (Apple Silicon)
pyinstaller --onefile --name backend-aarch64-apple-darwin main.py

# macOS (Intel)
pyinstaller --onefile --name backend-x86_64-apple-darwin main.py

# Linux
pyinstaller --onefile --name backend-x86_64-unknown-linux-gnu main.py
```

打包产物放入 `frontend/src-tauri/binaries/` 目录。

#### Tauri 完整打包

```bash
cd frontend
pnpm tauri build
```

产物：
- Windows：`frontend/src-tauri/target/release/bundle/msi/*.msi`
- macOS：`frontend/src-tauri/target/release/bundle/dmg/*.dmg`
- Linux：`frontend/src-tauri/target/release/bundle/appimage/*.AppImage`

#### OCR 扩展包（单独打包）

```bash
cd ocr-module
pyinstaller --onedir --name ocr-extension .
# 产出 ocr-extension/ 目录，压缩为 zip 分发
```

用户安装方式：将 OCR 扩展包解压到 `app_data/extensions/ocr/` 目录。

### 7.3 项目目录结构（开发时）

```text
price_comparison_scanner/
├── frontend/                    # Tauri + React 前端
│   ├── src/                     # React 源码
│   ├── src-tauri/               # Tauri Rust 配置和代码
│   │   ├── binaries/            # sidecar 可执行文件（打包时放入）
│   │   ├── tauri.conf.json
│   │   └── src/main.rs
│   ├── package.json
│   └── pnpm-lock.yaml
├── backend/                     # Python FastAPI 后端
│   ├── main.py                  # FastAPI 应用入口
│   ├── api/                     # API 路由
│   ├── services/                # 业务服务（ProjectService 等）
│   ├── engines/                 # 核心引擎（DocumentParser、RuleEngine 等）
│   ├── models/                  # 数据模型
│   ├── db/                      # SQLite 操作层
│   ├── requirements.txt
│   └── tests/
├── ocr-module/                  # OCR 可选模块（独立打包）
├── docs/                        # 文档
│   ├── requirements/
│   └── design/
└── CLAUDE.md
```

------

## 8. 扩展性与未来规划

| 方向 | 扩展方式 |
|------|----------|
| OCR 增强 | OCR 模块已独立，后续可替换引擎（如 Surya 等） |
| 语义归组 | CommodityGrouper 可插件化，后续加入 embedding 模型 |
| 性能优化 | pandas → Polars 替换；SQLite WAL 模式 |
| 规则能力增强 | 用户自定义品牌别名表、噪音词表 |
| 国际化 | 前端 i18n 框架（react-intl），后端标准字段已用英文列名 |
