# Phase 4：符合性审查 + 比价导出 — Phase Spec

> **文档优先级：** 本 phase-spec 及其下属 task-spec 的内容优先于 master-plan。若 master-plan 中有与本文档冲突的描述，以本文档为准。

## 目标

实现工作台第四步（符合性审查）和第五步（比价与导出）的完整链路：需求标准 CRUD + 导入导出 → 符合性匹配（keyword/numeric/manual）→ 比价计算 + 异常检测 + 双口径最低价 → 4 Sheet Excel 导出 → 跨阶段待处理问题清单。前端提供符合性审查页面、比价结果页面和全局问题面板。

**关键特性**：符合性审查为可选模块。不录入需求标准时，跳过符合性匹配，直接进入比价（effective_min_price = min_price）。

**不是** "一次做完所有高级分析"。自动单位换算、汇率换算、性价比评分模型等后续版本功能不在本 Phase 范围内。

## 边界

### 本 Phase 包含

- ComplianceEvaluator 引擎（需求标准管理 + keyword/numeric/manual 三类匹配）
- PriceComparator 引擎（比价计算 + 异常检测 + 双口径最低价）
- ReportGenerator 引擎（4 Sheet Excel 导出，无需求标准时 3 Sheet）
- 符合性 + 比价相关 Pydantic 模型
- 需求标准 CRUD API + 导入导出 API
- 符合性匹配 API（匹配 + 矩阵 + 确认 + 可接受标记）
- 比价 API（生成 + 查询）
- Excel 导出 API（异步）
- 待处理问题清单 API（跨阶段聚合）
- 符合性 + 比价数据库操作层（RequirementRepo, ComplianceRepo, ComparisonRepo）
- 符合性 + 比价服务层（ComplianceService, ComparisonService, ReportService, ProblemService）
- 前端 ComplianceStage（需求录入 + 符合性矩阵 + 证据面板）
- 前端 ComparisonStage（比价结果 + 异常高亮 + 导出）
- 前端 ProblemPanel（跨阶段问题清单，常驻面板）
- openapi.json 更新

### 本 Phase 不包含（明确排除）

- 自动单位换算（→ 后续版本）
- 自动汇率换算（→ 后续版本）
- 自动性价比评分模型（→ 后续版本）
- PDF 审计报告导出（→ 后续版本）
- 符合性匹配的语义模型 / LLM 辅助（→ 后续版本）
- Tauri sidecar 完整生命周期管理（→ Phase 5）
- 阶段导航 UI 完善（→ Phase 5）
- OCR 模块集成验证（→ Phase 5）
- 端到端验收数据集测试（→ Phase 5）

---

## 本 Phase 引入的新模块/文件

### 后端

```
backend/
├── engines/
│   ├── compliance_evaluator.py     # ComplianceEvaluator 引擎（需求管理 + 符合性匹配）
│   ├── price_comparator.py         # PriceComparator 引擎（比价计算 + 异常检测）
│   └── report_generator.py         # ReportGenerator 引擎（4 Sheet Excel 导出）
├── models/
│   ├── compliance.py               # 符合性相关 Pydantic 模型
│   └── comparison.py               # 比价 + 导出 + 问题清单 Pydantic 模型
├── db/
│   ├── requirement_repo.py         # requirement_items 表操作
│   ├── compliance_repo.py          # compliance_matches 表操作
│   └── comparison_repo.py          # comparison_results 表操作
├── services/
│   ├── compliance_service.py       # 符合性业务编排
│   ├── comparison_service.py       # 比价业务编排
│   ├── report_service.py           # 导出业务编排
│   └── problem_service.py          # 问题清单聚合
├── api/
│   ├── requirements.py             # 需求标准 CRUD + 导入导出路由
│   ├── compliance.py               # 符合性匹配路由
│   ├── comparison.py               # 比价路由
│   ├── export.py                   # Excel 导出路由
│   └── problems.py                 # 问题清单路由
└── tests/
    ├── test_compliance_evaluator.py
    ├── test_price_comparator.py
    ├── test_report_generator.py
    ├── test_requirement_repo.py
    ├── test_compliance_repo.py
    ├── test_comparison_repo.py
    ├── test_requirements_api.py
    ├── test_compliance_api.py
    ├── test_comparison_api.py
    ├── test_export_api.py
    └── test_problems_api.py
```

### 前端

```
frontend/src/
├── components/stages/
│   ├── compliance-stage.tsx          # 符合性审查主容器
│   ├── requirement-editor.tsx        # 需求标准录入/编辑
│   ├── requirement-importer.tsx      # 模板 Excel 导入
│   ├── compliance-matrix.tsx         # 符合性矩阵（横轴供应商 × 纵轴需求项）
│   ├── evidence-detail-panel.tsx     # 证据详情面板
│   ├── comparison-stage.tsx          # 比价与导出主容器
│   ├── comparison-table.tsx          # 比价结果表格
│   ├── anomaly-highlight.tsx         # 异常高亮组件
│   ├── export-button.tsx             # 导出按钮（含进度）
│   └── problem-panel.tsx             # 待处理问题清单面板
├── types/
│   ├── compliance.ts                 # 符合性相关 TypeScript 类型
│   └── comparison.ts                 # 比价 + 问题清单 TypeScript 类型
└── stores/
    ├── compliance-store.ts           # 符合性状态管理
    └── comparison-store.ts           # 比价 + 导出状态管理
```

---

## 任务列表与依赖关系

```
                    ┌── 4.11 Pydantic 模型 ─────────────────────────────────────────┐
                    │                                                                │
                    │         ┌── 4.1 需求标准 CRUD ── 4.2 符合性匹配 ── 4.3 符合性 API ──┐
                    │         │                                                       │    │
Phase 3 ───────────┤         │                                                       │    ├── 4.6 ReportGenerator
                    │         │                                                       │    │         │
                    │         └── 4.4 PriceComparator ───── 4.5 比价 API ──────────────┘    │         │
                    │                                                                      │         │
                    │                                                             4.7 问题清单 API ──── 4.12 openapi
                    │                                                                      │
                    │                                                                 ┌────┤
                    │                                                                 │    │
                    │                                                            4.8 ComplianceStage
                    │                                                                 │
                    │                                                            4.9 ComparisonStage
                    │                                                                 │
                    │                                                           4.10 ProblemPanel
                    │
                    └─────────────────────────────────────────────────────────────────────────
```

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 4.1 | ComplianceEvaluator — 需求标准 CRUD + 导入导出 | backend-dev | Phase 3, 4.11 |
| 4.2 | ComplianceEvaluator — 符合性匹配（keyword/numeric/manual） | backend-dev | 4.1 |
| 4.3 | 符合性 API（匹配 + 矩阵 + 确认 + 可接受标记） | backend-dev | 4.2 |
| 4.4 | PriceComparator — 比价计算 + 异常检测 + 双口径最低价 | backend-dev | Phase 3, 4.11 |
| 4.5 | 比价 API | backend-dev | 4.4 |
| 4.6 | ReportGenerator — 4 Sheet Excel 导出 | backend-dev | 4.3, 4.5 |
| 4.7 | 待处理问题清单 API | backend-dev | 4.3, 4.5 |
| 4.8 | 前端 ComplianceStage — 需求录入 + 符合性矩阵 + 证据面板 | frontend-dev | 4.3 |
| 4.9 | 前端 ComparisonStage — 比价结果 + 异常高亮 + 导出 | frontend-dev | 4.5, 4.6 |
| 4.10 | 前端 ProblemPanel — 跨阶段问题清单 | frontend-dev | 4.7 |
| 4.11 | 符合性 + 比价相关 Pydantic 模型 | backend-dev | Phase 3 |
| 4.12 | 更新 openapi.json + reviewer 审查 | backend-dev | 4.7 |

**并行化：**
- 4.11（Pydantic 模型）可最先启动，与其他后端任务并行
- 4.1-4.3（符合性链路）与 4.4-4.5（比价链路）可并行开发
- 4.6（ReportGenerator）依赖 4.3 和 4.5 都完成
- 4.7（问题清单）依赖 4.3 和 4.5 都完成
- 4.8/4.9/4.10 前端任务分别等待各自对应的后端 API 就绪
- 4.8 与 4.9/4.10 可并行
- 4.12 依赖 4.7 完成

---

## 完成标准（机器可判定）

### 后端验收

```bash
cd backend

# 1. 工程门禁全部通过
ruff check .                          # exit 0，零警告
mypy . --ignore-missing-imports       # exit 0，零错误
pytest -x -q                          # exit 0，全部通过

# 2. 引擎单元测试
pytest tests/test_compliance_evaluator.py -v   # 符合性匹配引擎全部通过
pytest tests/test_price_comparator.py -v       # 比价引擎全部通过
pytest tests/test_report_generator.py -v       # 导出引擎全部通过

# 3. API 集成测试
pytest tests/test_requirements_api.py -v       # 需求标准 API
pytest tests/test_compliance_api.py -v         # 符合性 API
pytest tests/test_comparison_api.py -v         # 比价 API
pytest tests/test_export_api.py -v             # 导出 API
pytest tests/test_problems_api.py -v           # 问题清单 API

# 4. 启动验证
DEV_MODE=1 uvicorn main:app --host 127.0.0.1 --port 17396 &
sleep 2

# 假设已有项目 $PROJECT_ID 且已完成归组

# 5. 需求标准 CRUD
REQ=$(curl -sf -X POST http://127.0.0.1:17396/api/projects/$PROJECT_ID/requirements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"内存不低于16GB","category":"技术规格","is_mandatory":true,"match_type":"numeric","expected_value":"16","operator":"gte"}')
REQ_ID=$(echo $REQ | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "✓ 创建需求项: $REQ_ID"

# 6. 符合性匹配
curl -sf -X POST http://127.0.0.1:17396/api/projects/$PROJECT_ID/compliance/evaluate \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'task_id' in data
print('✓ 符合性匹配任务已提交')
"

# 7. 比价生成
curl -sf -X POST http://127.0.0.1:17396/api/projects/$PROJECT_ID/comparison/generate \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'task_id' in data
print('✓ 比价任务已提交')
"

# 8. 获取比价结果
curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID/comparison \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
assert isinstance(data, list)
for r in data:
    assert r['comparison_status'] in ('comparable', 'blocked', 'partial')
    assert 'min_price' in r
    assert 'effective_min_price' in r
    assert 'supplier_prices' in r
print(f'✓ 比价结果: {len(data)} 个商品组')
"

# 9. 问题清单
curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID/problems \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
assert isinstance(data, list)
print(f'✓ 问题清单: {len(data)} 类问题')
"

# 10. Excel 导出
curl -sf -X POST http://127.0.0.1:17396/api/projects/$PROJECT_ID/export \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'task_id' in data
print('✓ 导出任务已提交')
"

kill %1
```

### 前端验收

```bash
cd frontend

# 1. 工程门禁全部通过
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0

# 2. 手动验证（需后端运行中）
# - 工作台第四步显示需求标准录入表单
# - 可新增/编辑/删除需求项
# - 可导入 Excel 模板
# - 执行符合性匹配后显示矩阵
# - 矩阵中可确认匹配结果、标记可接受
# - 点击单元格可查看证据详情
# - 不录入需求标准时可直接跳到第五步
# - 工作台第五步显示比价结果表格
# - 全量最低价和有效最低价正确高亮
# - 异常商品组有红色/黄色标识
# - 点击导出按钮 → 显示进度 → 下载 Excel
# - 问题面板常驻显示，按类型聚合
# - 点击问题项可跳转到对应阶段
```

### 契约验收

```bash
cd backend
python scripts/generate_openapi.py
python -c "
import json
with open('../docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())
# 需求标准 API
assert '/api/projects/{project_id}/requirements' in paths, 'Missing requirements'
assert '/api/requirements/{requirement_id}' in paths, 'Missing requirement by id'
assert '/api/projects/{project_id}/requirements/import' in paths, 'Missing requirements import'
assert '/api/projects/{project_id}/requirements/export' in paths, 'Missing requirements export'
# 符合性 API
assert '/api/projects/{project_id}/compliance/evaluate' in paths, 'Missing compliance evaluate'
assert '/api/projects/{project_id}/compliance/matrix' in paths, 'Missing compliance matrix'
assert '/api/compliance/{match_id}/confirm' in paths, 'Missing compliance confirm'
assert '/api/compliance/{match_id}/accept' in paths, 'Missing compliance accept'
# 比价 API
assert '/api/projects/{project_id}/comparison/generate' in paths, 'Missing comparison generate'
assert '/api/projects/{project_id}/comparison' in paths, 'Missing comparison'
# 导出 + 问题
assert '/api/projects/{project_id}/export' in paths, 'Missing export'
assert '/api/projects/{project_id}/problems' in paths, 'Missing problems'
print(f'✓ openapi.json Phase 4 API: 12 个路径已定义')
"
```

---

## 关键技术决策

### 符合性模块可选性

- compliance_status 初始值为 `skipped`
- 用户首次创建需求项时，compliance_status 自动切换为 `pending`
- 删除所有需求项后，compliance_status 回到 `skipped`
- 比价时检查：若 compliance_status == `skipped`，则 effective_min_price = min_price
- 前端 ComplianceStage 无需求标准时显示引导页面（"录入需求标准"或"跳过此步骤"）

### 异常检测规则（PRD 5.8）

| 异常类型 | 阻断级别 | 影响范围 |
|----------|----------|----------|
| 税价口径不一致 | 阻断 | 该商品组最低价结论 |
| 单位不一致 | 阻断 | 该商品组价格比较 |
| 币种不一致 | 阻断 | 涉及组的价格比较 |
| 必填字段缺失 | 标记 | 不阻断 |

### Excel 导出条件格式

- 全量最低价：绿色填充
- 有效最低价：蓝色边框（若有需求标准）
- 异常行：红色填充
- 部分符合可接受：黄色填充

### MCP 强制规则

- backend-dev 首次使用 `openpyxl` 写入 + 样式 API（PatternFill, Font, Alignment, Border 等）时，**必须**先通过 Context7 查文档确认用法
- frontend-dev 首次使用 TanStack Table 高级功能（列分组、固定列）时，**必须**先通过 Context7 查文档

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-4.1-compliance-crud.md`
- `task-4.2-compliance-matching.md`
- `task-4.3-compliance-api.md`
- `task-4.4-price-comparator.md`
- `task-4.5-comparison-api.md`
- `task-4.6-report-generator.md`
- `task-4.7-problems-api.md`
- `task-4.8-compliance-stage-ui.md`
- `task-4.9-comparison-stage-ui.md`
- `task-4.10-problem-panel-ui.md`
- `task-4.11-pydantic-models.md`
- `task-4.12-openapi-update.md`
