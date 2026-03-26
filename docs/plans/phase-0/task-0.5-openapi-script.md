# Task 0.5: OpenAPI 自动生成脚本 + 首次契约

## 输入条件

- Task 0.4 完成（projects 路由已注册，`main.py` 中有完整的 app）

## 输出物

- 修改: `backend/scripts/generate_openapi.py`（填充实现）
- 创建: `docs/api/openapi.json`（首次生成）

## 禁止修改

- 不修改 `api/` 下任何路由文件
- 不修改 `main.py`
- 不修改 `frontend/`
- 不修改 `db/`

## 实现规格

### scripts/generate_openapi.py

```python
#!/usr/bin/env python
"""
OpenAPI 契约自动生成脚本。
每次后端 API 路由变更后必须运行此脚本并提交 docs/api/openapi.json。

用法：
    cd backend
    python scripts/generate_openapi.py

输出：
    ../docs/api/openapi.json
"""
import json
import sys
from pathlib import Path

# 确保 backend 目录在 import path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

def main():
    spec = app.openapi()
    output_path = Path(__file__).parent.parent.parent / "docs" / "api" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 原子写入
    tmp_path = output_path.with_suffix(".tmp")
    data = json.dumps(spec, indent=2, ensure_ascii=False)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        import os
        os.fsync(f.fileno())
    tmp_path.replace(output_path)

    # 汇总信息
    paths = list(spec.get("paths", {}).keys())
    print(f"✓ 已生成 openapi.json: {len(paths)} 个路径")
    for p in sorted(paths):
        methods = list(spec["paths"][p].keys())
        print(f"  {', '.join(m.upper() for m in methods):12s} {p}")

if __name__ == "__main__":
    main()
```

### 首次运行

```bash
cd backend
python scripts/generate_openapi.py
```

预期输出：
```
✓ 已生成 openapi.json: 4 个路径
  GET          /api/health
  POST         /api/projects
  GET          /api/projects
  GET, DELETE  /api/projects/{project_id}
```

## 测试与验收

```bash
# 1. 脚本可执行
cd backend
python scripts/generate_openapi.py

# 2. 文件已生成
test -f ../docs/api/openapi.json

# 3. 内容正确
python -c "
import json
with open('../docs/api/openapi.json') as f:
    spec = json.load(f)
paths = set(spec['paths'].keys())
required = {'/api/health', '/api/projects', '/api/projects/{project_id}'}
missing = required - paths
assert not missing, f'缺少路径: {missing}'
print(f'✓ openapi.json 验证通过: {len(paths)} 个路径')
"

# 4. 幂等性：再次生成，内容应相同
python scripts/generate_openapi.py
git diff --exit-code ../docs/api/openapi.json
echo "✓ 幂等性验证通过"
```

**断言清单：**
- `docs/api/openapi.json` 文件存在
- 包含 `/api/health`、`/api/projects`、`/api/projects/{project_id}` 路径
- 重复执行不产生 diff
- MCP 服务可加载此文件（手动验证）

## 提交

```bash
git add backend/scripts/generate_openapi.py docs/api/openapi.json
git commit -m "Phase 0.5: OpenAPI 自动生成脚本 + 首次接口契约"
```
