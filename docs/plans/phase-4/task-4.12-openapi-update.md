# Task 4.12: 更新 openapi.json + reviewer 审查

## 输入条件

- Task 4.7 完成（所有后端 API 已实现）
- 后端可正常启动

## 输出物

- 修改: `docs/api/openapi.json`（重新生成）
- reviewer 审查记录

## 禁止修改

- 不修改 `backend/` 源代码
- 不修改 `frontend/`
- 仅重新生成 `docs/api/openapi.json`

## 实现规格

### 步骤 1：重新生成 openapi.json

```bash
cd backend
python scripts/generate_openapi.py
```

### 步骤 2：验证生成的 openapi.json

```bash
python -c "
import json
with open('../docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())

# Phase 4 新增路径验证
required_paths = [
    '/api/projects/{project_id}/requirements',
    '/api/requirements/{requirement_id}',
    '/api/projects/{project_id}/requirements/import',
    '/api/projects/{project_id}/requirements/export',
    '/api/projects/{project_id}/compliance/evaluate',
    '/api/projects/{project_id}/compliance/matrix',
    '/api/compliance/{match_id}/confirm',
    '/api/compliance/{match_id}/accept',
    '/api/projects/{project_id}/comparison/generate',
    '/api/projects/{project_id}/comparison',
    '/api/projects/{project_id}/export',
    '/api/projects/{project_id}/problems',
]

missing = [p for p in required_paths if p not in paths]
if missing:
    print(f'✗ 缺失路径: {missing}')
    exit(1)
print(f'✓ openapi.json 已包含所有 Phase 4 路径（{len(required_paths)} 个）')
print(f'✓ 总路径数: {len(paths)}')

# 验证关键 schema
schemas = list(spec.get('components', {}).get('schemas', {}).keys())
required_schemas = [
    'RequirementCreate', 'RequirementResponse',
    'ComplianceMatrixResponse', 'ComplianceConfirmRequest',
    'ComparisonResultResponse', 'ComparisonGenerateResponse',
    'ExportResponse', 'ProblemGroup',
]
missing_schemas = [s for s in required_schemas if s not in schemas]
if missing_schemas:
    print(f'✗ 缺失 Schema: {missing_schemas}')
    exit(1)
print(f'✓ 关键 Schema 已定义（{len(required_schemas)} 个）')
"
```

### 步骤 3：reviewer 审查

提交给 reviewer 进行以下审查：

1. **契约一致性**：openapi.json 中的路径、参数、请求体、响应体与实际 API 代码一致
2. **模型完整性**：所有 Pydantic 模型正确映射到 OpenAPI schema
3. **前后端契约**：前端 types/ 定义与 openapi.json 中的 schema 一致
4. **设计文档对照**：API 路由与技术架构 5.1 节定义一致
5. **代码质量**：Phase 4 新增代码符合分层约束和命名规范

## 测试与验收

```bash
cd backend

# 1. 重新生成并检查
python scripts/generate_openapi.py

# 2. 验证无 diff（若已经是最新）
# git diff --exit-code ../docs/api/openapi.json

# 3. 验证路径和 schema
python -c "
import json
with open('../docs/api/openapi.json') as f:
    spec = json.load(f)

# 验证 Phase 0-4 所有路径都存在
all_expected = [
    '/api/health',
    '/api/projects',
    '/api/projects/{id}',
    '/api/projects/{id}/requirements',
    '/api/requirements/{id}',
    '/api/projects/{id}/requirements/import',
    '/api/projects/{id}/requirements/export',
    '/api/projects/{id}/compliance/evaluate',
    '/api/projects/{id}/compliance/matrix',
    '/api/compliance/{id}/confirm',
    '/api/compliance/{id}/accept',
    '/api/projects/{id}/comparison/generate',
    '/api/projects/{id}/comparison',
    '/api/projects/{id}/export',
    '/api/projects/{id}/problems',
]
paths = list(spec.get('paths', {}).keys())
for p in all_expected:
    assert p in paths, f'Missing: {p}'
print(f'✓ 所有路径验证通过 ({len(all_expected)} 个)')
"
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| generate_openapi.py 执行成功 | exit 0 |
| 12 个 Phase 4 路径存在 | 全部 assert 通过 |
| 8 个关键 Schema 存在 | 全部 assert 通过 |
| reviewer 审查通过 | 无阻塞问题 |

## 提交

```bash
git add docs/api/openapi.json
git commit -m "Phase 4.12: 更新 openapi.json — Phase 4 完整接口契约（需求/符合性/比价/导出/问题清单）"
```
