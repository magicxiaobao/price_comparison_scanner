-- ============================================================
-- 项目基本信息（含阶段状态，合并为单表）
-- ============================================================
-- 注意：每次打开项目数据库时必须执行 PRAGMA foreign_keys = ON;
-- 数据库版本通过 schema_version 表管理，支持后续迁移

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'));

CREATE TABLE IF NOT EXISTS projects (
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
CREATE TABLE IF NOT EXISTS supplier_files (
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
CREATE TABLE IF NOT EXISTS raw_tables (
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
CREATE TABLE IF NOT EXISTS standardized_rows (
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
CREATE TABLE IF NOT EXISTS commodity_groups (
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

CREATE TABLE IF NOT EXISTS group_members (
    group_id TEXT NOT NULL REFERENCES commodity_groups(id) ON DELETE CASCADE,
    standardized_row_id TEXT NOT NULL REFERENCES standardized_rows(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, standardized_row_id)
);

-- ============================================================
-- 比价结果（持久化，避免重复计算）
-- ============================================================
CREATE TABLE IF NOT EXISTS comparison_results (
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
CREATE TABLE IF NOT EXISTS audit_logs (
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
CREATE TABLE IF NOT EXISTS requirement_items (
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
CREATE TABLE IF NOT EXISTS compliance_matches (
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
CREATE INDEX IF NOT EXISTS idx_requirement_project ON requirement_items(project_id);
CREATE INDEX IF NOT EXISTS idx_compliance_requirement ON compliance_matches(requirement_item_id);
CREATE INDEX IF NOT EXISTS idx_compliance_group ON compliance_matches(commodity_group_id);
CREATE INDEX IF NOT EXISTS idx_compliance_supplier ON compliance_matches(supplier_file_id);
CREATE INDEX IF NOT EXISTS idx_std_rows_supplier ON standardized_rows(supplier_file_id);
CREATE INDEX IF NOT EXISTS idx_std_rows_table ON standardized_rows(raw_table_id);
CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_row ON group_members(standardized_row_id);
CREATE INDEX IF NOT EXISTS idx_comparison_group ON comparison_results(group_id);
CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_id);
