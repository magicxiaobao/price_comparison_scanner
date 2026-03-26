# Task 1.10: 更新 openapi.json + reviewer 审查

## 输入条件

- Task 1.5 完成（所有 Phase 1 后端 API 路由就绪）

## 输出物

- 修改: `docs/api/openapi.json`（更新为包含 Phase 1 新增路由的完整契约）

## 禁止修改

- 不修改 `backend/` 任何源代码
- 不修改 `frontend/`

## 实现规格

### 生成 openapi.json

```bash
cd backend
python scripts/generate_openapi.py
```

或等效命令：

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

### 契约校验

生成后必须校验以下路由存在：

| 方法 | 路径 | 来源 |
|------|------|------|
| POST | `/api/projects/{project_id}/files` | Task 1.5 |
| GET | `/api/projects/{project_id}/files` | Task 1.5 |
| PUT | `/api/files/{file_id}/confirm-supplier` | Task 1.5 |
| GET | `/api/projects/{project_id}/tables` | Task 1.5 |
| PUT | `/api/tables/{table_id}/toggle-selection` | Task 1.5 |
| GET | `/api/tasks/{task_id}/status` | Task 1.1 |
| DELETE | `/api/tasks/{task_id}` | Task 1.1 |

### reviewer 审查清单

reviewer 使用 `review` skill 审查以下内容：

1. **契约完整性**：openapi.json 包含所有 Phase 1 新增路由
2. **请求体/响应体一致性**：openapi.json 中的 schema 与实际 Pydantic 模型一致
3. **路径参数命名一致性**：与技术架构 5.1 节定义的路由路径一致
4. **HTTP 方法正确性**：上传用 POST，确认用 PUT，查询用 GET，取消用 DELETE
5. **错误响应定义**：404（不存在）、400（参数错误）、409（冲突）都有定义

### reviewer 重点检查项

- `POST /api/projects/{id}/files` 是否正确声明 multipart/form-data
- `PUT /api/files/{id}/confirm-supplier` 的请求体是否包含 supplier_name 和 project_id
- `GET /api/tasks/{id}/status` 的响应是否包含 status/progress/error 字段
- 所有 Phase 0 的路由仍然存在且未被破坏

## 测试与验收

```bash
# 1. 重新生成 openapi.json
cd backend
python scripts/generate_openapi.py

# 2. 校验路由完整性
python -c "
import json
with open('../docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())

# Phase 0 路由仍存在
assert any('/health' in p for p in paths), 'Missing /api/health'
assert any('/projects' in p and '{' not in p for p in paths), 'Missing /api/projects'

# Phase 1 新增路由
phase1_routes = [
    'files',           # POST /api/projects/{id}/files
    'confirm-supplier', # PUT /api/files/{id}/confirm-supplier
    'tables',          # GET /api/projects/{id}/tables
    'toggle-selection', # PUT /api/tables/{id}/toggle-selection
    'tasks',           # GET /api/tasks/{id}/status
]
for route in phase1_routes:
    found = any(route in p for p in paths)
    assert found, f'Missing route containing: {route}'
    print(f'✓ 路由包含 {route}')

# 检查 schema 定义
schemas = list(spec.get('components', {}).get('schemas', {}).keys())
print(f'✓ openapi.json: {len(paths)} 个路径, {len(schemas)} 个 schema')
"

# 3. 确认文件已更新
git diff --stat docs/api/openapi.json
```

**断言清单：**
- openapi.json 包含所有 Phase 0 + Phase 1 路由
- 所有 Phase 1 路由的请求/响应 schema 与 Pydantic 模型一致
- `git diff` 显示 openapi.json 有变更

## 提交

```bash
git add docs/api/openapi.json
git commit -m "Phase 1.10: 更新 openapi.json — 新增文件导入/任务状态/供应商确认/表格选择路由"
```
