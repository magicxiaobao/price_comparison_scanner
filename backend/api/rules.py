from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from config import settings
from engines.rule_engine import RuleEngine
from models.rule import RuleCreateUpdate, RuleSet, RuleTestRequest

router = APIRouter(tags=["规则管理"])


def _get_engine() -> RuleEngine:
    rules_dir = Path(settings.APP_DATA_DIR) / "rules"
    return RuleEngine(rules_dir)


@router.get("/rules")
async def get_rules() -> dict:
    """获取全局规则"""
    engine = _get_engine()
    return engine.load_global_rules().model_dump(by_alias=True)


@router.get("/rules/templates")
async def list_templates() -> list[dict]:
    """获取可用模板列表"""
    engine = _get_engine()
    return engine.list_templates()


@router.post("/rules/load-template")
async def load_template(body: dict) -> dict:
    """加载指定模板到当前用户规则"""
    template_id = body.get("templateId")
    if not template_id:
        raise HTTPException(400, "templateId 必填")
    engine = _get_engine()
    try:
        engine.apply_template(template_id)
    except FileNotFoundError as e:
        raise HTTPException(404, f"模板 {template_id} 不存在") from e
    return engine.load_global_rules().model_dump(by_alias=True)


@router.put("/rules")
async def upsert_rule(rule: RuleCreateUpdate) -> dict:
    """新增规则"""
    engine = _get_engine()
    try:
        result = engine.add_rule(rule.model_dump(by_alias=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return result.model_dump(by_alias=True)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str) -> dict:
    """删除规则"""
    engine = _get_engine()
    deleted = engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, "规则不存在")
    return {"detail": "已删除"}


@router.put("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str) -> dict:
    """启用/停用规则"""
    engine = _get_engine()
    try:
        new_state = engine.toggle_rule(rule_id)
    except ValueError as e:
        raise HTTPException(404, "规则不存在") from e
    return {"enabled": new_state}


@router.post("/rules/import")
async def import_rules(
    file: Annotated[UploadFile, File()], strategy: str = "ask"
) -> dict:
    """导入规则 JSON 文件"""
    content = await file.read()
    try:
        imported = RuleSet.model_validate_json(content)
    except Exception as e:
        raise HTTPException(400, "无效的规则 JSON 文件") from e
    engine = _get_engine()
    return engine.import_rules(imported, strategy)


@router.get("/rules/export")
async def export_rules() -> StreamingResponse:
    """导出规则 JSON 文件下载"""
    engine = _get_engine()
    rule_set = engine.export_rules()
    content = rule_set.model_dump_json(by_alias=True, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=rules-export.json"},
    )


@router.post("/rules/reset-default")
async def reset_default() -> dict:
    """恢复默认模板"""
    engine = _get_engine()
    engine.reset_default()
    return engine.load_global_rules().model_dump(by_alias=True)


@router.post("/rules/test")
async def test_rule(req: RuleTestRequest) -> dict:
    """测试规则匹配"""
    engine = _get_engine()
    result = engine.test_rule(req.column_name)
    return result.model_dump(by_alias=True)
