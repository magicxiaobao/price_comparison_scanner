# Phase 1：文件导入 — Phase Spec

> **文档优先级：** 本 phase-spec 及其下属 task-spec 的内容优先于 master-plan。若 master-plan 中有与本文档冲突的描述，以本文档为准。

## 目标

用户可以上传供应商文件（xlsx/docx/pdf），系统通过 TaskManager 异步解析出表格（RawTable），用户确认供应商名称并选择参与比价的表格。本 Phase 完成后，工作台第一步「导入文件」可完整操作。

**不是** "把所有引擎和数据模型一次做完"。RuleEngine、TableStandardizer、AuditLogService 等留到 Phase 2。

## 边界

### 本 Phase 包含

- TaskManager 异步任务框架（ThreadPoolExecutor 实现）+ 任务状态 API
- DocumentParser 引擎（Excel / Word / PDF-L1 解析器）
- 文件导入相关 Pydantic 模型（SupplierFile、RawTable、TaskStatus、TaskInfo）
- 文件导入 API（上传 + 供应商确认 + 表格选择 + 表格列表）
- 前端 ImportStage 组件（文件上传 + 解析进度 + 供应商确认 + 表格选择）
- 前端 ProjectStore 扩展（阶段状态刷新）
- openapi.json 更新

### 本 Phase 不包含（明确排除）

- RuleEngine 规则引擎（→ Phase 2）
- TableStandardizer 标准化引擎（→ Phase 2）
- AuditLogService 操作留痕（→ Phase 2）
- 失效传播机制 `_propagate_dirty()`（→ Phase 2）
- PDF L2（转图片 OCR）/ L3（人工介入）的实际实现（仅接口占位）
- OCR 模块安装与集成（→ Phase 5）
- 图片文件（JPG/PNG/TIFF）导入（→ Phase 5）
- 前端 StandardizeStage 及后续阶段组件（→ Phase 2+）

---

## 本 Phase 引入的新模块/文件

### 后端新增

```
backend/
├── engines/
│   ├── document_parser.py        # DocumentParser 引擎（parse + _parse_xlsx/_parse_docx/_parse_pdf）
│   └── task_manager.py           # TaskManager（submit/get_status/get_progress/cancel/get_result）
├── models/
│   ├── file.py                   # SupplierFile 相关 Pydantic 模型
│   ├── table.py                  # RawTable 相关 Pydantic 模型
│   └── task.py                   # TaskStatus, TaskInfo Pydantic 模型
├── db/
│   ├── file_repo.py              # supplier_files 表 CRUD
│   └── table_repo.py             # raw_tables 表 CRUD
├── services/
│   └── file_service.py           # 文件导入业务编排（上传 + 解析 + 供应商确认 + 表格选择）
├── api/
│   ├── files.py                  # 文件导入相关路由（/api/projects/{id}/files 等）
│   └── tasks.py                  # 任务状态路由（/api/tasks/{id}/status 等）
└── tests/
    ├── test_task_manager.py
    ├── test_document_parser.py
    ├── test_file_repo.py
    ├── test_table_repo.py
    ├── test_file_api.py
    └── test_task_api.py
```

### 前端新增

```
frontend/src/
├── components/
│   └── stages/
│       ├── import-stage.tsx       # ImportStage 容器组件
│       ├── file-uploader.tsx      # 文件上传区域（拖拽 + 点击）
│       ├── supplier-confirm-dialog.tsx  # 供应商名称确认对话框
│       └── table-selector.tsx     # 表格选择列表
├── types/
│   ├── file.ts                   # SupplierFile, RawTable 类型
│   └── task.ts                   # TaskStatus, TaskInfo 类型
└── lib/
    └── api.ts                    # 新增文件导入相关 API 调用（修改）
```

---

## 任务列表与依赖关系

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 1.1 | TaskManager 异步任务框架 + 任务状态 API | backend-dev | Phase 0 |
| 1.2 | DocumentParser — Excel 解析器 | backend-dev | Phase 0 |
| 1.3 | DocumentParser — Word 解析器 | backend-dev | Phase 0 |
| 1.4 | DocumentParser — PDF 结构化解析器（L1 only） | backend-dev | Phase 0 |
| 1.5 | 文件导入 API + 供应商确认 API + 表格选择 API | backend-dev | 1.1, 1.2, 1.3, 1.4, 1.6 |
| 1.6 | 文件导入相关 Pydantic 模型 | backend-dev | Phase 0 |
| 1.7 | 前端 ImportStage — 文件上传 + 解析进度 | frontend-dev | 1.5, 1.10 |
| 1.8 | 前端 ImportStage — 供应商确认 + 表格选择 | frontend-dev | 1.5, 1.10 |
| 1.9 | 前端 ProjectStore 扩展（阶段状态） | frontend-dev | 1.7 |
| 1.10 | 更新 openapi.json + reviewer 审查 | backend-dev | 1.5 |

### 依赖关系图

```
Phase 0 完成
    │
    ├── 1.1 TaskManager ──────────────────────┐
    │                                          │
    ├── 1.2 Excel 解析器 ─────────────────────┤
    │                                          │
    ├── 1.3 Word 解析器 ──────────────────────┤
    │                                          │
    ├── 1.4 PDF 解析器 ───────────────────────┤
    │                                          │
    └── 1.6 Pydantic 模型 ────────────────────┤
                                               │
                                          1.5 文件导入 API ── 1.10 openapi 更新
                                               │                    │
                                               │              ┌─────┤
                                               │              │     │
                                          1.7 文件上传UI ─────┘     │
                                               │                    │
                                          1.8 供应商确认UI ─────────┘
                                               │
                                          1.9 ProjectStore 扩展
```

### 并行化机会

- **1.1 / 1.2 / 1.3 / 1.4 / 1.6** 全部可并行（都仅依赖 Phase 0）
- **1.2 / 1.3 / 1.4** 三个解析器完全独立，可同时开发
- **1.7 / 1.8** 都依赖 1.5 和 1.10，可在 API 就绪后并行开发
- **1.9** 依赖 1.7

---

## 完成标准（机器可判定）

### 后端验收

```bash
cd backend

# 1. 工程门禁全部通过
ruff check .                          # exit 0
mypy . --ignore-missing-imports       # exit 0
pytest -x -q                          # exit 0，全部通过

# 2. 启动后端
DEV_MODE=1 uvicorn main:app --host 127.0.0.1 --port 17396 &
sleep 2

# 3. 创建测试项目
PROJECT=$(curl -sf -X POST http://127.0.0.1:17396/api/projects \
  -H 'Content-Type: application/json' \
  -d '{"name": "Phase1验收"}')
PROJECT_ID=$(echo $PROJECT | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. 上传 Excel 文件 → 返回 task_id
UPLOAD_RESP=$(curl -sf -X POST http://127.0.0.1:17396/api/projects/$PROJECT_ID/files \
  -F "file=@test_fixtures/sample.xlsx")
echo $UPLOAD_RESP | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'task_id' in data, 'Missing task_id'
assert 'file_id' in data, 'Missing file_id'
print(f'✓ 上传返回 task_id={data[\"task_id\"]}, file_id={data[\"file_id\"]}')
"
TASK_ID=$(echo $UPLOAD_RESP | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
FILE_ID=$(echo $UPLOAD_RESP | python -c "import sys,json; print(json.load(sys.stdin)['file_id'])")

# 5. 轮询任务状态直到完成
for i in $(seq 1 20); do
  STATUS=$(curl -sf http://127.0.0.1:17396/api/tasks/$TASK_ID/status)
  S=$(echo $STATUS | python -c "import sys,json; print(json.load(sys.stdin)['status'])")
  [ "$S" = "completed" ] && break
  [ "$S" = "failed" ] && echo "✗ 任务失败" && break
  sleep 1
done
echo $STATUS | python -c "
import sys, json
data = json.load(sys.stdin)
assert data['status'] == 'completed', f'Expected completed, got {data[\"status\"]}'
print('✓ 任务完成')
"

# 6. 获取表格列表
curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID/tables | python -c "
import sys, json
data = json.load(sys.stdin)
assert len(data) >= 1, 'Expected at least 1 table'
print(f'✓ 解析出 {len(data)} 个表格')
"

# 7. 确认供应商名称
curl -sf -X PUT http://127.0.0.1:17396/api/files/$FILE_ID/confirm-supplier \
  -H 'Content-Type: application/json' \
  -d '{"supplier_name": "测试供应商"}' | python -c "
import sys, json
data = json.load(sys.stdin)
assert data['supplier_confirmed'] == True
print('✓ 供应商已确认')
"

# 8. 切换表格选择
TABLE_ID=$(curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID/tables | \
  python -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -sf -X PUT http://127.0.0.1:17396/api/tables/$TABLE_ID/toggle-selection | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'selected' in data
print(f'✓ 表格选择切换成功，当前 selected={data[\"selected\"]}')
"

# 9. 取消任务 API 可达
curl -sf -X DELETE http://127.0.0.1:17396/api/tasks/nonexistent-id \
  -o /dev/null -w "%{http_code}" | grep -q "404" && echo "✓ 取消不存在的任务 → 404"

kill %1
```

### 前端验收

```bash
cd frontend

# 1. 工程门禁
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0

# 2. 手动验证项目（需后端运行）
# - 进入项目工作台 → 显示「导入文件」阶段
# - 拖拽或点击上传 .xlsx/.docx/.pdf 文件 → 显示解析进度条
# - 解析完成 → 弹出供应商确认对话框（预填猜测名称）
# - 确认供应商名称 → 显示表格列表
# - 可勾选/取消表格参与比价
# - 上传多个文件 → 文件列表正确展示
```

### 契约验收

```bash
# openapi.json 包含新增路由
python -c "
import json
with open('docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())
required = [
    '/api/projects/{id}/files',
    '/api/files/{id}/confirm-supplier',
    '/api/projects/{id}/tables',
    '/api/tables/{id}/toggle-selection',
    '/api/tasks/{id}/status',
]
for r in required:
    # openapi.json 中路径参数可能用 {project_id} 等不同名称，做模糊检查
    found = any(r.split('{')[0] in p for p in paths)
    assert found, f'Missing {r}'
    print(f'✓ {r}')
print(f'✓ openapi.json 包含所有 Phase 1 路由（共 {len(paths)} 个路径）')
"
```

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-1.1-task-manager.md`
- `task-1.2-excel-parser.md`
- `task-1.3-word-parser.md`
- `task-1.4-pdf-parser.md`
- `task-1.5-file-import-api.md`
- `task-1.6-pydantic-models.md`
- `task-1.7-import-stage-upload.md`
- `task-1.8-import-stage-confirm.md`
- `task-1.9-project-store-extension.md`
- `task-1.10-openapi-update.md`
