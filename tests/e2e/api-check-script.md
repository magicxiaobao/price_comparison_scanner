# API 级自动化检查步骤

> 基于 DS-1 数据集的完整 API 流程验证。
> 所有请求需携带 `Authorization: Bearer <session_token>` 头。
> 后端地址：`http://127.0.0.1:17396`

## 环境准备

```bash
# 启动后端
cd backend
uvicorn main:app --host 127.0.0.1 --port 17396 --reload

# 设置变量
BASE=http://127.0.0.1:17396
TOKEN="test-session-token"  # dev 模式下的 session token
AUTH="Authorization: Bearer $TOKEN"
```

---

## Step 1: 健康检查

```bash
curl -s "$BASE/api/health" | python -m json.tool
```

- **端点**: `GET /api/health`
- **预期响应**: `{"status": "ok"}` 或类似
- **断言**: HTTP 200，响应包含 status 字段

---

## Step 2: 创建项目

```bash
curl -s -X POST "$BASE/api/projects" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"name": "DS-1 API 测试", "description": "标准场景验收"}' \
  | python -m json.tool
```

- **端点**: `POST /api/projects`
- **请求体**: `ProjectCreate` — `{"name": "...", "description": "..."}`
- **预期响应**: `ProjectDetail` — 包含 `id`、`name`、`status`、`created_at`
- **断言**:
  - HTTP 200
  - 响应包含 `id`（UUID 字符串）
  - `name` == "DS-1 API 测试"
- **保存**: `PROJECT_ID` = 响应中的 `id`

```bash
PROJECT_ID=$(curl -s -X POST "$BASE/api/projects" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"name": "DS-1 API 测试", "description": "标准场景验收"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "PROJECT_ID=$PROJECT_ID"
```

---

## Step 3: 上传文件（3 个 xlsx）

对 DS-1 的 3 个文件逐一上传：

```bash
# 文件 1：联想科技
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/files" \
  -H "$AUTH" \
  -F "file=@tests/e2e/test-data/ds-1/联想科技-办公设备报价.xlsx" \
  | python -m json.tool

# 文件 2：华硕经销
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/files" \
  -H "$AUTH" \
  -F "file=@tests/e2e/test-data/ds-1/华硕经销-办公设备报价单.xlsx" \
  | python -m json.tool

# 文件 3：戴尔直销
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/files" \
  -H "$AUTH" \
  -F "file=@tests/e2e/test-data/ds-1/戴尔直销-报价函.xlsx" \
  | python -m json.tool
```

- **端点**: `POST /api/projects/{project_id}/files`（multipart/form-data）
- **预期响应**: `FileUploadResponse` — 包含 `file_id`、`task_id`
- **断言**:
  - HTTP 200
  - 每次上传返回 `file_id` 和 `task_id`
- **保存**: 3 个 `FILE_ID` 和 3 个 `TASK_ID`

### 等待解析任务完成

```bash
# 轮询每个上传任务直到 completed
poll_task() {
  local tid=$1
  while true; do
    STATUS=$(curl -s "$BASE/api/tasks/$tid/status" -H "$AUTH" \
      | python -c "import sys,json; print(json.load(sys.stdin)['status'])")
    echo "Task $tid: $STATUS"
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then break; fi
    sleep 2
  done
}

poll_task $TASK_ID_1
poll_task $TASK_ID_2
poll_task $TASK_ID_3
```

- **端点**: `GET /api/tasks/{task_id}/status`
- **预期响应**: `TaskStatusResponse` — `status` 从 `pending` -> `running` -> `completed`
- **断言**: 所有 3 个任务最终 `status == "completed"`

---

## Step 4: 查看文件列表 & 确认供应商

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/files" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/files`
- **预期响应**: 3 个 `SupplierFileResponse` 对象
- **断言**:
  - 返回 3 个文件
  - 每个文件的 `guessed_supplier_name` 不为空（预期：联想科技 / 华硕经销 / 戴尔直销）

### 确认每个供应商名称

```bash
# 对每个 FILE_ID 确认供应商名称
curl -s -X PUT "$BASE/api/files/$FILE_ID_1/confirm-supplier" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"supplier_name": "联想科技"}' \
  | python -m json.tool

curl -s -X PUT "$BASE/api/files/$FILE_ID_2/confirm-supplier" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"supplier_name": "华硕经销"}' \
  | python -m json.tool

curl -s -X PUT "$BASE/api/files/$FILE_ID_3/confirm-supplier" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"supplier_name": "戴尔直销"}' \
  | python -m json.tool
```

- **端点**: `PUT /api/files/{file_id}/confirm-supplier`
- **请求体**: `SupplierConfirmRequest` — `{"supplier_name": "..."}`
- **预期响应**: `SupplierFileResponse` — `supplier_name` 已更新
- **断言**: HTTP 200，`supplier_name` 与请求一致

---

## Step 5: 查看表格 & 选择参与比价

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/tables" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/tables`
- **预期响应**: `RawTableResponse[]` — 每个文件至少 1 个表格
- **断言**:
  - 返回 >= 3 个表格
  - 每个表格有 `table_id`、`sheet_name`
- **保存**: 各 `TABLE_ID`

### 选择表格参与比价

```bash
# 对每个 TABLE_ID 启用
curl -s -X PUT "$BASE/api/tables/$TABLE_ID_1/toggle-selection" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"selected": true}' \
  | python -m json.tool
# ... 对 TABLE_ID_2, TABLE_ID_3 重复
```

- **端点**: `PUT /api/tables/{table_id}/toggle-selection`
- **请求体**: `TableToggleRequest` — `{"selected": true}`
- **预期响应**: `TableToggleResponse`
- **断言**: HTTP 200

---

## Step 6: 触发标准化

```bash
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/standardize" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d 'null' \
  | python -m json.tool
```

- **端点**: `POST /api/projects/{project_id}/standardize`
- **请求体**: `StandardizeRequest | null`
- **预期响应**: `StandardizeTaskResponse` — 包含 `task_id`
- **保存**: `STD_TASK_ID`

### 轮询标准化任务

```bash
poll_task $STD_TASK_ID
```

- **断言**: `status == "completed"`

---

## Step 7: 查看标准化结果

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/standardized-rows" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/standardized-rows`
- **预期响应**: `StandardizedRowResponse[]` — 15 行（每供应商 5 行）
- **断言**:
  - 返回 15 行
  - 每行包含 `product_name`、`specification`、`unit`、`unit_price` 等标准字段

### 查看列名映射详情

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/column-mapping-info" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/column-mapping-info`
- **断言**: 返回各供应商的列名映射信息，检查自动映射命中数

---

## Step 8: 触发归组

```bash
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/grouping/generate" \
  -H "$AUTH" \
  | python -m json.tool
```

- **端点**: `POST /api/projects/{project_id}/grouping/generate`
- **预期响应**: `GroupingGenerateResponse` — 包含 `task_id`
- **保存**: `GROUP_TASK_ID`

### 轮询归组任务

```bash
poll_task $GROUP_TASK_ID
```

- **断言**: `status == "completed"`

---

## Step 9: 查看归组结果 & 确认归组

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/groups" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/groups`
- **预期响应**: `CommodityGroupResponse[]` — 5 个组
- **断言**:
  - 返回 5 个组
  - 每个组的 `confidence_level` == "medium"（DS-1 品牌不同触发硬约束）
  - 每个组包含 3 个成员
- **保存**: 各 `GROUP_ID`

### 确认每个归组

```bash
# 对每个 GROUP_ID 确认
curl -s -X PUT "$BASE/api/groups/$GROUP_ID_1/confirm" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm"}' \
  | python -m json.tool
# ... 对 GROUP_ID_2 ~ GROUP_ID_5 重复
```

- **端点**: `PUT /api/groups/{group_id}/confirm`
- **请求体**: `GroupActionRequest` — `{"action": "confirm"}`
- **预期响应**: `GroupConfirmResponse`
- **断言**: HTTP 200

---

## Step 10: 触发比价

```bash
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/comparison/generate" \
  -H "$AUTH" \
  | python -m json.tool
```

- **端点**: `POST /api/projects/{project_id}/comparison/generate`
- **预期响应**: `ComparisonGenerateResponse` — 包含 `task_id`
- **保存**: `CMP_TASK_ID`

### 轮询比价任务

```bash
poll_task $CMP_TASK_ID
```

- **断言**: `status == "completed"`

### 查看比价结果

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/comparison" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/comparison`
- **预期响应**: `ComparisonResultResponse[]` — 5 组比价结果
- **断言**:
  - 返回 5 组
  - 笔记本电脑组最低价为 3899
  - 27 寸显示器组最低价为 1899
  - 无线键鼠套装组最低价为 99
  - 扩展坞组最低价为 799
  - 激光打印机组最低价为 1599
  - 无异常标记

---

## Step 11: 查看问题清单

```bash
curl -s "$BASE/api/projects/$PROJECT_ID/problems" -H "$AUTH" | python -m json.tool
```

- **端点**: `GET /api/projects/{project_id}/problems`
- **预期响应**: `ProblemGroup[]`
- **断言**: DS-1 应无阻塞性问题（可能有信息性提示）

---

## Step 12: 导出 Excel

```bash
curl -s -X POST "$BASE/api/projects/$PROJECT_ID/export" \
  -H "$AUTH" \
  | python -m json.tool
```

- **端点**: `POST /api/projects/{project_id}/export`
- **预期响应**: `ExportResponse` — 包含 `taskId`
- **保存**: `EXPORT_TASK_ID`

### 轮询导出任务

```bash
# 轮询直到完成，completed 时 result 包含文件路径
EXPORT_RESULT=$(curl -s "$BASE/api/tasks/$EXPORT_TASK_ID/status" -H "$AUTH")
echo $EXPORT_RESULT | python -m json.tool
```

- **端点**: `GET /api/tasks/{task_id}/status`
- **断言**:
  - `status == "completed"`
  - `result` 字段包含导出文件路径信息（`filePath` / `fileName`）

---

## Step 13: 下载导出文件

> 注：导出文件通过 `TaskStatusResponse.result` 中的文件路径获取。
> dev 模式下文件保存在后端本地目录，可直接通过文件系统访问。
> 如有专用下载端点，使用该端点；否则直接检查文件存在性。

```bash
# 从 task result 中提取文件路径
FILE_PATH=$(echo $EXPORT_RESULT | python -c "
import sys, json
data = json.load(sys.stdin)
result = data.get('result', {})
if isinstance(result, str):
    import json as j
    result = j.loads(result)
print(result.get('filePath', result.get('file_path', 'NOT_FOUND')))
")
echo "Export file: $FILE_PATH"

# 验证文件存在
ls -la "$FILE_PATH"
```

- **断言**:
  - 文件存在且大小 > 0
  - 文件扩展名为 .xlsx

---

## Step 14: 清理（可选）

```bash
curl -s -X DELETE "$BASE/api/projects/$PROJECT_ID" \
  -H "$AUTH" \
  | python -m json.tool
```

- **端点**: `DELETE /api/projects/{project_id}`
- **断言**: HTTP 200

---

## Python requests 版本（完整脚本骨架）

```python
"""DS-1 API 自动化检查脚本"""
import requests
import time

BASE = "http://127.0.0.1:17396"
TOKEN = "test-session-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
TEST_DATA = "tests/e2e/test-data/ds-1"

FILES = [
    ("联想科技-办公设备报价.xlsx", "联想科技"),
    ("华硕经销-办公设备报价单.xlsx", "华硕经销"),
    ("戴尔直销-报价函.xlsx", "戴尔直销"),
]

def poll_task(task_id, timeout=60):
    """轮询异步任务直到完成"""
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/api/tasks/{task_id}/status", headers=HEADERS)
        data = r.json()
        status = data["status"]
        print(f"  Task {task_id}: {status} ({data.get('progress', '')})")
        if status == "completed":
            return data
        if status == "failed":
            raise Exception(f"Task failed: {data}")
        time.sleep(2)
    raise TimeoutError(f"Task {task_id} timed out")

# Step 1: Health check
r = requests.get(f"{BASE}/api/health")
assert r.status_code == 200, f"Health check failed: {r.status_code}"
print("[PASS] Health check")

# Step 2: Create project
r = requests.post(f"{BASE}/api/projects", headers=HEADERS,
                   json={"name": "DS-1 API 测试", "description": "标准场景验收"})
assert r.status_code == 200
project = r.json()
PROJECT_ID = project["id"]
print(f"[PASS] Created project: {PROJECT_ID}")

# Step 3: Upload files
file_ids = []
for filename, supplier in FILES:
    with open(f"{TEST_DATA}/{filename}", "rb") as f:
        r = requests.post(f"{BASE}/api/projects/{PROJECT_ID}/files",
                          headers=HEADERS, files={"file": (filename, f)})
    assert r.status_code == 200
    data = r.json()
    file_ids.append(data["file_id"])
    poll_task(data["task_id"])
    print(f"[PASS] Uploaded & parsed: {filename}")

# Step 4: Confirm suppliers
for file_id, (_, supplier) in zip(file_ids, FILES):
    r = requests.put(f"{BASE}/api/files/{file_id}/confirm-supplier",
                     headers=HEADERS, json={"supplier_name": supplier})
    assert r.status_code == 200
print("[PASS] Suppliers confirmed")

# Step 5: Select tables
r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/tables", headers=HEADERS)
tables = r.json()
assert len(tables) >= 3, f"Expected >= 3 tables, got {len(tables)}"
for t in tables:
    r = requests.put(f"{BASE}/api/tables/{t['table_id']}/toggle-selection",
                     headers=HEADERS, json={"selected": True})
    assert r.status_code == 200
print(f"[PASS] Selected {len(tables)} tables")

# Step 6: Run standardization
r = requests.post(f"{BASE}/api/projects/{PROJECT_ID}/standardize",
                   headers=HEADERS, json=None)
assert r.status_code == 200
poll_task(r.json()["task_id"])
print("[PASS] Standardization completed")

# Step 7: Check standardized rows
r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/standardized-rows", headers=HEADERS)
rows = r.json()
assert len(rows) == 15, f"Expected 15 rows, got {len(rows)}"
print(f"[PASS] Standardized rows: {len(rows)}")

# Check column mapping
r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/column-mapping-info", headers=HEADERS)
mappings = r.json()
print(f"[INFO] Column mappings: {len(mappings)} suppliers")

# Step 8: Generate grouping
r = requests.post(f"{BASE}/api/projects/{PROJECT_ID}/grouping/generate", headers=HEADERS)
assert r.status_code == 200
poll_task(r.json()["task_id"])
print("[PASS] Grouping completed")

# Step 9: Check & confirm groups
r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/groups", headers=HEADERS)
groups = r.json()
assert len(groups) == 5, f"Expected 5 groups, got {len(groups)}"
for g in groups:
    assert g["confidence_level"] == "medium", \
        f"Group '{g.get('group_name','')}' confidence={g['confidence_level']}, expected medium"
    r = requests.put(f"{BASE}/api/groups/{g['group_id']}/confirm",
                     headers=HEADERS, json={"action": "confirm"})
    assert r.status_code == 200
print("[PASS] All 5 groups confirmed (all medium confidence)")

# Step 10: Generate comparison
r = requests.post(f"{BASE}/api/projects/{PROJECT_ID}/comparison/generate", headers=HEADERS)
assert r.status_code == 200
poll_task(r.json()["task_id"])
print("[PASS] Comparison completed")

# Check comparison results
r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/comparison", headers=HEADERS)
results = r.json()
assert len(results) == 5, f"Expected 5 comparison results, got {len(results)}"
print(f"[PASS] Comparison results: {len(results)} groups")

# Step 11: Check problems
r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/problems", headers=HEADERS)
problems = r.json()
print(f"[INFO] Problems: {len(problems)} groups")

# Step 12: Export
r = requests.post(f"{BASE}/api/projects/{PROJECT_ID}/export", headers=HEADERS)
assert r.status_code == 200
export_result = poll_task(r.json()["taskId"])
print("[PASS] Export completed")

# Step 13: Verify export file
result = export_result.get("result", {})
if isinstance(result, str):
    import json
    result = json.loads(result)
file_path = result.get("filePath", result.get("file_path"))
if file_path:
    import os
    assert os.path.exists(file_path), f"Export file not found: {file_path}"
    assert os.path.getsize(file_path) > 0, "Export file is empty"
    print(f"[PASS] Export file exists: {file_path}")
else:
    print("[WARN] Could not extract file path from task result")

print("\n=== DS-1 API Check: ALL PASSED ===")
```

---

## API 端点速查表

| 步骤 | Method | 端点 | 说明 |
|------|--------|------|------|
| 健康检查 | GET | `/api/health` | 系统健康状态 |
| 创建项目 | POST | `/api/projects` | 创建新项目 |
| 上传文件 | POST | `/api/projects/{project_id}/files` | multipart 上传 |
| 任务轮询 | GET | `/api/tasks/{task_id}/status` | 异步任务状态 |
| 文件列表 | GET | `/api/projects/{project_id}/files` | 项目文件列表 |
| 确认供应商 | PUT | `/api/files/{file_id}/confirm-supplier` | 确认供应商名称 |
| 表格列表 | GET | `/api/projects/{project_id}/tables` | 已解析表格 |
| 选择表格 | PUT | `/api/tables/{table_id}/toggle-selection` | 切换参与比价 |
| 触发标准化 | POST | `/api/projects/{project_id}/standardize` | 异步标准化 |
| 标准化结果 | GET | `/api/projects/{project_id}/standardized-rows` | 标准化行 |
| 列名映射 | GET | `/api/projects/{project_id}/column-mapping-info` | 映射详情 |
| 触发归组 | POST | `/api/projects/{project_id}/grouping/generate` | 异步归组 |
| 归组结果 | GET | `/api/projects/{project_id}/groups` | 归组列表 |
| 确认归组 | PUT | `/api/groups/{group_id}/confirm` | 确认归组 |
| 触发比价 | POST | `/api/projects/{project_id}/comparison/generate` | 异步比价 |
| 比价结果 | GET | `/api/projects/{project_id}/comparison` | 比价结果 |
| 问题清单 | GET | `/api/projects/{project_id}/problems` | 待处理问题 |
| 触发导出 | POST | `/api/projects/{project_id}/export` | 异步导出 |
| 删除项目 | DELETE | `/api/projects/{project_id}` | 清理 |
