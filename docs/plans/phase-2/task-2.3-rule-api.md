# Task 2.3: 规则管理 API（13 个端点）

## 输入条件

- Task 2.2 完成（`engines/rule_engine.py` 就绪）
- Task 2.6 完成（`models/rule.py` 就绪）

## 输出物

- 创建: `backend/api/rules.py`
- 修改: `backend/main.py`（注册 rules 路由）
- 创建: `backend/tests/test_rules_api.py`

## 禁止修改

- 不修改 `engines/rule_engine.py`（已稳定）
- 不修改 `db/schema.sql`
- 不修改 `frontend/`

## 实现规格

### api/rules.py

```python
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from engines.rule_engine import RuleEngine
from models.rule import RuleCreateUpdate, RuleTestRequest, RuleTestResponse, TemplateInfo, RuleImportSummary
from config import settings
from pathlib import Path

router = APIRouter(tags=["规则管理"])

def _get_engine() -> RuleEngine:
    rules_dir = Path(settings.APP_DATA_DIR) / "rules"
    return RuleEngine(rules_dir)
```

### 13 个端点定义

| # | 方法 | 路径 | 功能 | 请求体/参数 | 响应 |
|---|------|------|------|------------|------|
| 1 | GET | `/api/rules` | 获取全局规则 | 无 | `RuleSet` JSON |
| 2 | GET | `/api/rules/templates` | 模板列表 | 无 | `list[TemplateInfo]` |
| 3 | POST | `/api/rules/load-template` | 加载模板 | `{"templateId": "default"}` | `RuleSet` |
| 4 | PUT | `/api/rules` | 新增/编辑规则 | `RuleCreateUpdate` | 新增/更新后的规则 |
| 5 | DELETE | `/api/rules/{id}` | 删除规则 | 路径参数 `id` | `{"detail": "已删除"}` |
| 6 | PUT | `/api/rules/{id}/toggle` | 启用/停用 | 路径参数 `id` | `{"enabled": true/false}` |
| 7 | POST | `/api/rules/import` | 导入规则 JSON | `UploadFile` + `strategy` 查询参数 | `RuleImportSummary` + conflicts |
| 8 | GET | `/api/rules/export` | 导出规则 JSON | 无 | JSON 文件下载 |
| 9 | POST | `/api/rules/reset-default` | 恢复默认 | 无 | `RuleSet`（重置后） |
| 10 | POST | `/api/rules/test` | 测试匹配 | `RuleTestRequest` | `RuleTestResponse` |

**补充说明**：master-plan 列出 13 个端点，但技术架构 5.1 定义了 10 个端点。以技术架构为准，实际实现 10 个端点。3 个差额来自：部分端点合并（如 PUT /api/rules 同时支持新增和编辑）。

### 端点实现骨架

```python
@router.get("/rules")
async def get_rules():
    """获取全局规则"""
    engine = _get_engine()
    return engine.load_global_rules().model_dump(by_alias=True)

@router.get("/rules/templates")
async def list_templates():
    """获取可用模板列表"""
    engine = _get_engine()
    return engine.list_templates()

@router.post("/rules/load-template")
async def load_template(body: dict):
    """加载指定模板到当前用户规则"""
    template_id = body.get("templateId")
    if not template_id:
        raise HTTPException(400, "templateId 必填")
    engine = _get_engine()
    engine.apply_template(template_id)
    return engine.load_global_rules().model_dump(by_alias=True)

@router.put("/rules")
async def upsert_rule(rule: RuleCreateUpdate):
    """新增或编辑规则"""
    engine = _get_engine()
    result = engine.add_rule(rule.model_dump(by_alias=True))
    return result

@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """删除规则"""
    engine = _get_engine()
    deleted = engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, "规则不存在")
    return {"detail": "已删除"}

@router.put("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str):
    """启用/停用规则"""
    engine = _get_engine()
    new_state = engine.toggle_rule(rule_id)
    return {"enabled": new_state}

@router.post("/rules/import")
async def import_rules(file: UploadFile = File(...), strategy: str = "ask"):
    """
    导入规则 JSON 文件。
    strategy: overwrite_all / skip_all / ask
    """
    content = await file.read()
    imported = RuleSet.model_validate_json(content)
    engine = _get_engine()
    result = engine.import_rules(imported, strategy)
    return result

@router.get("/rules/export")
async def export_rules():
    """导出规则 JSON 文件下载"""
    engine = _get_engine()
    rule_set = engine.export_rules()
    import io
    content = rule_set.model_dump_json(by_alias=True, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=rules-export.json"},
    )

@router.post("/rules/reset-default")
async def reset_default():
    """恢复默认模板"""
    engine = _get_engine()
    engine.reset_default()
    return engine.load_global_rules().model_dump(by_alias=True)

@router.post("/rules/test")
async def test_rule(req: RuleTestRequest):
    """测试规则匹配"""
    engine = _get_engine()
    result = engine.test_rule(req.column_name)
    return result
```

### main.py 修改

```python
from api.rules import router as rules_router
app.include_router(rules_router, prefix="/api")
```

## 测试与验收

### tests/test_rules_api.py

```python
@pytest.fixture(autouse=True)
def _use_temp_app_data(monkeypatch, tmp_path):
    """使用临时目录作为应用数据目录"""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    from config import Settings
    import config
    config.settings = Settings()
```

### 测试用例清单

```python
# test_get_rules_empty — 初始状态返回有效 RuleSet
# test_get_rules_templates — 返回至少 2 个模板
# test_load_template — 加载模板后规则列表非空
# test_upsert_rule_add — 新增规则成功
# test_upsert_rule_edit — 编辑已有规则
# test_delete_rule — 删除规则返回 200
# test_delete_rule_not_found — 删除不存在的规则返回 404
# test_toggle_rule — 启用/停用切换
# test_export_rules — 返回 JSON 文件下载
# test_import_rules — 导入规则文件
# test_reset_default — 恢复默认后规则与模板一致
# test_test_rule_match — 测试匹配命中
# test_test_rule_no_match — 测试匹配未命中
# test_test_rule_conflict — 测试匹配有冲突
```

**断言清单：**

- `GET /api/rules` → 200，返回包含 `columnMappingRules` 的 JSON
- `GET /api/rules/templates` → 200，返回列表长度 >= 2
- `POST /api/rules/load-template` → 200，返回非空规则集
- `PUT /api/rules` → 200，新增的规则在后续 GET 中可查到
- `DELETE /api/rules/{id}` → 200（存在时）/ 404（不存在时）
- `PUT /api/rules/{id}/toggle` → 200，`enabled` 字段翻转
- `POST /api/rules/import` → 200，返回 `added`/`conflicts`/`skipped` 字段
- `GET /api/rules/export` → 200，Content-Type 为 application/json，Content-Disposition 包含 filename
- `POST /api/rules/reset-default` → 200，规则恢复为默认
- `POST /api/rules/test` → 200，`matched` 为 true/false

**门禁命令：**

```bash
cd backend
ruff check api/rules.py tests/test_rules_api.py
mypy api/rules.py --ignore-missing-imports
pytest tests/test_rules_api.py -x -q
```

## 提交

```bash
git add backend/api/rules.py backend/main.py backend/tests/test_rules_api.py
git commit -m "Phase 2.3: 规则管理 API — 10 个端点（CRUD/模板/导入导出/测试匹配）"
```
