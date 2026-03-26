# Task 2.10: 更新 openapi.json + reviewer 审查

## 输入条件

- Task 2.3 完成（规则管理 API 就绪）
- Task 2.5 完成（标准化 API + 手工修正 API 就绪）
- 所有后端 API 路由已注册到 `main.py`

## 输出物

- 修改: `docs/api/openapi.json`（重新生成）

## 禁止修改

- 不修改 `backend/` 源码（仅运行生成脚本）
- 不修改 `frontend/` 源码
- 不修改 `docs/` 下除 `openapi.json` 以外的文件

## 实现规格

### 生成流程

```bash
cd backend
python scripts/generate_openapi.py
```

或等价命令：

```bash
cd backend
python -c "
import json
from main import app
spec = app.openapi()
with open('../docs/api/openapi.json', 'w', encoding='utf-8') as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)
"
```

### 生成后验证

生成的 `openapi.json` 必须包含以下端点：

**规则管理端点：**
- `GET /api/rules`
- `GET /api/rules/templates`
- `POST /api/rules/load-template`
- `PUT /api/rules`
- `DELETE /api/rules/{id}`
- `PUT /api/rules/{id}/toggle`
- `POST /api/rules/import`
- `GET /api/rules/export`
- `POST /api/rules/reset-default`
- `POST /api/rules/test`

**标准化端点：**
- `POST /api/projects/{id}/standardize`
- `GET /api/projects/{id}/standardized-rows`
- `PUT /api/standardized-rows/{id}`

### reviewer 审查清单

reviewer 收到审查任务后，按以下清单逐项检查：

1. **契约完整性**：所有 Phase 2 新增 API 端点在 openapi.json 中有定义
2. **请求体一致性**：API 请求体与 Pydantic 模型定义一致
3. **响应体一致性**：API 响应体与 Pydantic 模型定义一致
4. **路径参数**：`{id}` 参数类型为 string
5. **HTTP 方法**：与技术架构 5.1 定义一致
6. **错误响应**：404/400/422 等错误响应有定义
7. **前后端类型对齐**：前端 `types/rule.ts` 和 `types/standardization.ts` 与 openapi.json Schema 一致
8. **命名规范**：响应字段使用 camelCase（通过 Pydantic alias）

## 测试与验收

```bash
# 1. openapi.json 存在且内容有效
test -f docs/api/openapi.json

# 2. 包含规则和标准化端点
python -c "
import json
with open('docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())

# 规则端点
assert '/api/rules' in paths, 'Missing /api/rules'
assert '/api/rules/templates' in paths, 'Missing /api/rules/templates'
assert '/api/rules/load-template' in paths, 'Missing /api/rules/load-template'
assert '/api/rules/{id}' in paths or '/api/rules/{rule_id}' in paths, 'Missing /api/rules/{id}'
assert '/api/rules/{id}/toggle' in paths or '/api/rules/{rule_id}/toggle' in paths, 'Missing /api/rules/{id}/toggle'
assert '/api/rules/import' in paths, 'Missing /api/rules/import'
assert '/api/rules/export' in paths, 'Missing /api/rules/export'
assert '/api/rules/reset-default' in paths, 'Missing /api/rules/reset-default'
assert '/api/rules/test' in paths, 'Missing /api/rules/test'

# 标准化端点
std_paths = [p for p in paths if 'standardize' in p or 'standardized' in p]
assert len(std_paths) >= 2, f'Expected at least 2 standardization paths, got {std_paths}'

print(f'✓ openapi.json: {len(paths)} 个路径，规则 + 标准化端点完整')
"

# 3. Schema 定义存在
python -c "
import json
with open('docs/api/openapi.json') as f:
    spec = json.load(f)
schemas = list(spec.get('components', {}).get('schemas', {}).keys())
print(f'✓ Schema 定义: {len(schemas)} 个')
# 检查关键 schema
assert any('Rule' in s for s in schemas), 'Missing Rule-related schema'
"

# 4. 与后端代码一致性
cd backend
python -c "
from main import app
spec = app.openapi()
import json
with open('../docs/api/openapi.json') as f:
    committed = json.load(f)
assert json.dumps(spec, sort_keys=True) == json.dumps(committed, sort_keys=True), 'openapi.json is stale'
print('✓ openapi.json 与后端代码一致')
"
```

**断言清单：**

- `docs/api/openapi.json` 文件存在
- 包含所有 Phase 2 新增的 API 路径
- Schema 定义包含规则和标准化相关模型
- 文件内容与后端 `app.openapi()` 输出一致（无遗漏提交）
- reviewer 审查通过所有 8 项检查

## 提交

```bash
git add docs/api/openapi.json
git commit -m "Phase 2.10: 更新 openapi.json — 新增规则管理 + 标准化 API 契约"
```
