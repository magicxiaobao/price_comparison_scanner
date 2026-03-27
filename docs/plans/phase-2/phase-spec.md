# Phase 2：规则引擎 + 标准化 — Phase Spec

> **文档优先级：** 本 phase-spec 及其下属 task-spec 的内容优先于 master-plan。若 master-plan 中有与本文档冲突的描述，以本文档为准。

## 前置条件

- Phase 1 全部任务已完成（10/10），P1 阻塞项已修复（commit `39cc91d`）
- **Phase 1 carry-over 必带项已收口或已纳入本 Phase 执行波次**（详见 [`carry-over.md`](carry-over.md)）

## 目标

实现全局规则管理（列名映射 + 值标准化）和表格标准化引擎，用户可通过规则将导入的原始表格统一映射为 9 个标准字段，预览标准化结果并进行手工修正。同时引入 AuditLogService 操作留痕和失效传播机制，为后续归组/比价阶段提供数据基础。

## 边界

### 本 Phase 包含

- AuditLogService 操作留痕（审计日志写入 audit_logs 表）
- RuleEngine 引擎（规则加载 / 匹配 / 冲突解决 / 项目级覆盖）
- 规则管理 API（10 个端点：CRUD + 模板 + 导入导出 + 测试）
- TableStandardizer 引擎（列名映射 + 值标准化 + 总价自动计算 + source_location 追溯 + 规则快照）
- 标准化 API + 手工修正 API + 失效传播
- 标准化相关 Pydantic 模型（StandardizedRow、SourceLocation、Rule、RuleSet、MatchResult 等）
- 前端 RuleManagement 页面（RuleList + RuleEditor + RuleTestPanel + ImportExportPanel）
- 前端 StandardizeStage（ColumnMappingPanel + StandardizedDataTable 可编辑表格）
- 前端 RuleStore（Zustand）
- 内置默认模板（通用采购 + IT 设备）
- 更新 openapi.json

### 本 Phase 不包含（明确排除）

- 商品归组（CommodityGrouper）（→ Phase 3）
- 符合性审查（ComplianceEvaluator）（→ Phase 4）
- 比价计算（PriceComparator）（→ Phase 4）
- Excel 导出（ReportGenerator）（→ Phase 4）
- 项目级规则覆盖的自动回写全局机制（MVP 仅提供手动"保存到全局规则"按钮）
- 品牌别名表 / 噪音词表（→ Phase 3 归组引擎使用）

---

## 本 Phase 引入的新模块/文件

### 后端

```
backend/
├── services/
│   └── audit_log_service.py      # AuditLogService — 操作留痕
├── engines/
│   ├── rule_engine.py            # RuleEngine — 规则加载/匹配/冲突解决
│   └── table_standardizer.py     # TableStandardizer — 字段映射 + 值标准化
├── models/
│   ├── rule.py                   # 规则相关 Pydantic 模型
│   └── standardization.py        # 标准化相关 Pydantic 模型
├── api/
│   ├── rules.py                  # 规则管理 10 个端点
│   └── standardization.py        # 标准化 + 手工修正 API
├── db/
│   ├── audit_log_repo.py         # 审计日志 CRUD
│   └── standardized_row_repo.py  # 标准化行 CRUD
└── tests/
    ├── test_audit_log.py
    ├── test_rule_engine.py
    ├── test_table_standardizer.py
    ├── test_rules_api.py
    └── test_standardization_api.py
```

### 前端

```
frontend/src/
├── app/
│   └── rule-management.tsx        # 规则管理页面（填充 Phase 0 占位）
├── components/
│   ├── rules/
│   │   ├── rule-list.tsx
│   │   ├── rule-editor.tsx
│   │   ├── rule-test-panel.tsx
│   │   └── import-export-panel.tsx
│   └── stages/
│       └── standardize-stage.tsx
│           ├── column-mapping-panel.tsx
│           └── standardized-data-table.tsx
├── stores/
│   └── rule-store.ts              # RuleStore
└── types/
    ├── rule.ts                    # 规则相关类型
    └── standardization.ts         # 标准化相关类型
```

### 全局数据文件

```
app_data/rules/
├── default-template.json          # 内置通用采购模板
├── it-device-template.json        # 内置 IT 设备模板
└── user-rules.json                # 用户自定义规则（首次启动时从模板复制）
```

---

## 任务列表与依赖关系

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 2.1 | AuditLogService 操作留痕 | backend-dev | Phase 1 |
| 2.2 | RuleEngine — 规则加载/管理/冲突解决 | backend-dev | 2.6 |
| 2.3 | 规则管理 API（10 个端点） | backend-dev | 2.2, 2.6 |
| 2.4 | TableStandardizer — 字段映射 + 值标准化 | backend-dev | 2.2, 2.6 |
| 2.5 | 标准化 API + 手工修正 API + 失效传播 | backend-dev | 2.1, 2.4, 2.6 |
| 2.6 | 标准化相关 Pydantic 模型 | backend-dev | Phase 1 |
| 2.7 | 前端 RuleManagement 页面 | frontend-dev | 2.9, 2.10 |
| 2.8 | 前端 StandardizeStage — 预览 + 可编辑表格 + 手工修正 | frontend-dev | 2.5, 2.9(弱), 2.10 |
| 2.9 | 前端 RuleStore | frontend-dev | 2.3, 2.10 |
| 2.10 | 更新 openapi.json + reviewer 审查 | backend-dev | 2.3, 2.5 |

### 依赖关系图

```
Phase 1 完成
  │
  ├── 2.1 AuditLogService ─────────────────────────┐
  │   (仅依赖 Phase 1，与 2.6 无硬依赖)             │
  │                                                 │
  └── 2.6 Pydantic 模型 ───────────────────────┐   │
      │                                         │   │
      └── 2.2 RuleEngine ──┬── 2.3 规则 API ───┤   │
                            │                   │   │
                            └── 2.4 Standardizer┤   │
                                                │   │
                                                └───┘
                                                │
                                           2.5 标准化 API
                                                │
                                     ┌──────────┘
                                     │
                                2.10 openapi.json 生成 + 审查
                                     │ （前端开工的契约基线）
                                     │
                          ┌──────────┼──────────┐
                          │          │          │
                     2.9 RuleStore   │          │
                     (依赖 2.3,     │          │
                      2.10)         │          │
                          │          │          │
                          ▼          │          │
                   2.7 RuleManagement│     2.8 StandardizeStage
                   (依赖 2.9, 2.10) │     (依赖 2.5, 2.10)
```

### 并行化机会

- **Preflight（carry-over 必带项）：** B4（python-multipart 依赖，已验证修复）+ B2（tasks.py response_model）+ B3（raw_data 反序列化）由 backend-dev 修复；F1（SupplierConfirmDialog stale name）由 frontend-dev 修复。详见 [`carry-over.md`](carry-over.md)。Preflight 全部确认通过后进入正式 Wave。
- **第一波：** 2.6（Pydantic 模型）— 无前置依赖，后端其他任务的类型基础
- **第二波（同波次）：** 2.1（AuditLog）+ 2.2（RuleEngine）。2.2 硬依赖 2.6；2.1 无硬依赖 2.6，排入本波次为推荐执行顺序（确保 Pydantic 模型就绪后再开始业务模块）。可并行仅在有多个 backend agent 时成立。
- **第三波（同波次）：** 2.3（规则 API，依赖 2.2）+ 2.4（Standardizer，依赖 2.2 + 2.6）。单 backend-dev 时串行执行。
- **第四波：** 2.5（标准化 API，依赖 2.1 + 2.4 + 2.6）
- **第五波：** 2.10（openapi.json 生成 + reviewer 后端审查，依赖 2.3 + 2.5）— 前端开工的契约基线
- **第六波：** 2.9（RuleStore，依赖 2.3 + 2.10）
- **第七波（同波次）：** 2.7（RuleManagement，依赖 2.9 + 2.10）+ 2.8（StandardizeStage，依赖 2.5 + 2.10）。单 frontend-dev 时串行执行。

---

## 完成标准（机器可判定）

### 后端验收

```bash
cd backend

# 1. 工程门禁全部通过
ruff check .                           # exit 0，零警告
mypy . --ignore-missing-imports        # exit 0，零错误
pytest -x -q                           # exit 0，全部通过

# 2. 启动后端
DEV_MODE=1 uvicorn main:app --host 127.0.0.1 --port 17396 &
sleep 2

# 3. 规则管理 API 可用
# 获取规则列表
curl -sf http://127.0.0.1:17396/api/rules | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'columnMappingRules' in data or isinstance(data, dict)
print('✓ 规则列表 OK')
"

# 模板列表
curl -sf http://127.0.0.1:17396/api/rules/templates | python -c "
import sys, json
data = json.load(sys.stdin)
assert len(data) >= 2, 'Expected at least 2 templates'
print(f'✓ 模板列表: {len(data)} 个')
"

# 规则测试
curl -sf -X POST http://127.0.0.1:17396/api/rules/test \
  -H 'Content-Type: application/json' \
  -d '{"columnName": "单价"}' | python -c "
import sys, json
data = json.load(sys.stdin)
assert data['matched'] == True
assert data['targetField'] == 'unit_price'
print('✓ 规则测试 OK')
"

# 4. 标准化 API（需先有项目和导入文件）
# 此处仅验证端点可达
HTTP_CODE=\$(curl -s -o /dev/null -w '%{http_code}' \
  -X POST http://127.0.0.1:17396/api/projects/nonexistent/standardize)
[ "\$HTTP_CODE" = "404" ] && echo "✓ 标准化 API 端点可达" || echo "✗ 预期 404，得到 \$HTTP_CODE"

# 5. 审计日志验证（通过手工修正触发）
# 需在集成测试中验证：修正 standardized_row → audit_logs 有记录 → 下游 dirty

kill %1
```

### 前端验收

```bash
cd frontend

# 1. 工程门禁全部通过
pnpm lint                              # exit 0
pnpm tsc --noEmit                      # exit 0

# 2. 手动验证
# - 导航到 #/rules → 规则管理页面可正常显示
# - 规则列表展示内置规则
# - 可新增/编辑/删除/启用停用规则
# - 规则测试面板：输入列名 → 显示映射结果
# - 导入/导出规则 JSON
# - 项目工作台 → 标准化阶段 → 列名映射面板 + 标准化预览表格
# - 表格可编辑，修正后有修改标记
```

### 契约验收

```bash
# openapi.json 已更新且包含规则和标准化端点
python -c "
import json
with open('docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())
assert '/api/rules' in paths, 'Missing /api/rules'
assert '/api/rules/test' in paths, 'Missing /api/rules/test'
assert '/api/rules/templates' in paths, 'Missing /api/rules/templates'
assert '/api/projects/{id}/standardize' in paths or any('standardize' in p for p in paths), 'Missing standardize'
assert '/api/standardized-rows/{id}' in paths or any('standardized-rows' in p for p in paths), 'Missing standardized-rows'
print(f'✓ openapi.json: 规则 + 标准化端点已包含')
"
```

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-2.1-audit-log.md`
- `task-2.2-rule-engine.md`
- `task-2.3-rule-api.md`
- `task-2.4-table-standardizer.md`
- `task-2.5-standardization-api.md`
- `task-2.6-pydantic-models.md`
- `task-2.7-rule-management-page.md`
- `task-2.8-standardize-stage.md`
- `task-2.9-rule-store.md`
- `task-2.10-openapi-update.md`
