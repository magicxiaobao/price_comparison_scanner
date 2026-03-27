"""Task 2.3: 规则管理 API 测试"""
import json
from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _use_temp_app_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> Generator[None, None, None]:
    """使用临时目录作为应用数据目录"""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("SESSION_TOKEN", "")
    import config
    from config import Settings

    original = config.settings
    config.settings = Settings()
    yield
    config.settings = original


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


# ── GET /api/rules ──


@pytest.mark.anyio
async def test_get_rules_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert "columnMappingRules" in data
    assert "valueNormalizationRules" in data


# ── GET /api/rules/templates ──


@pytest.mark.anyio
async def test_get_rules_templates(client: AsyncClient) -> None:
    resp = await client.get("/api/rules/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    ids = [t["id"] for t in data]
    assert "default" in ids
    assert "it-device" in ids


# ── POST /api/rules/load-template ──


@pytest.mark.anyio
async def test_load_template(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/rules/load-template", json={"templateId": "default"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["columnMappingRules"]) >= 9


@pytest.mark.anyio
async def test_load_template_missing_id(client: AsyncClient) -> None:
    resp = await client.post("/api/rules/load-template", json={})
    assert resp.status_code == 400


# ── PUT /api/rules (add) ──


@pytest.mark.anyio
async def test_upsert_rule_add(client: AsyncClient) -> None:
    resp = await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["单价"],
        "targetField": "unit_price",
        "matchMode": "exact",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["targetField"] == "unit_price"
    assert "id" in data

    # Verify it appears in GET /api/rules
    resp2 = await client.get("/api/rules")
    rules = resp2.json()["columnMappingRules"]
    assert any(r["id"] == data["id"] for r in rules)


@pytest.mark.anyio
async def test_upsert_rule_invalid_target(client: AsyncClient) -> None:
    resp = await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["xxx"],
        "targetField": "invalid_field",
    })
    assert resp.status_code == 400


# ── DELETE /api/rules/{id} ──


@pytest.mark.anyio
async def test_delete_rule(client: AsyncClient) -> None:
    # Add first
    resp = await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["单价"],
        "targetField": "unit_price",
    })
    rule_id = resp.json()["id"]

    resp2 = await client.delete(f"/api/rules/{rule_id}")
    assert resp2.status_code == 200
    assert resp2.json()["detail"] == "已删除"


@pytest.mark.anyio
async def test_delete_rule_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/api/rules/nonexistent-id")
    assert resp.status_code == 404


# ── PUT /api/rules/{id}/toggle ──


@pytest.mark.anyio
async def test_toggle_rule(client: AsyncClient) -> None:
    resp = await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["单价"],
        "targetField": "unit_price",
    })
    rule_id = resp.json()["id"]

    resp2 = await client.put(f"/api/rules/{rule_id}/toggle")
    assert resp2.status_code == 200
    assert resp2.json()["enabled"] is False

    resp3 = await client.put(f"/api/rules/{rule_id}/toggle")
    assert resp3.json()["enabled"] is True


# ── GET /api/rules/export ──


@pytest.mark.anyio
async def test_export_rules(client: AsyncClient) -> None:
    # Add a rule first
    await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["单价"],
        "targetField": "unit_price",
    })
    resp = await client.get("/api/rules/export")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert "filename=rules-export.json" in resp.headers.get("content-disposition", "")
    data = json.loads(resp.content)
    assert "columnMappingRules" in data


# ── POST /api/rules/import ──


@pytest.mark.anyio
async def test_import_rules(client: AsyncClient) -> None:
    rule_json = json.dumps({
        "version": "1.0",
        "columnMappingRules": [
            {
                "id": "imp-1",
                "sourceKeywords": ["品名"],
                "targetField": "product_name",
                "matchMode": "exact",
                "createdAt": "2026-01-01T00:00:00Z",
            }
        ],
        "valueNormalizationRules": [],
    })
    resp = await client.post(
        "/api/rules/import",
        files={"file": ("rules.json", rule_json, "application/json")},
        params={"strategy": "skip_all"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "added" in data
    assert "skipped" in data
    assert data["total"] == 1


# ── POST /api/rules/reset-default ──


@pytest.mark.anyio
async def test_reset_default(client: AsyncClient) -> None:
    # Add custom rule
    await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["自定义"],
        "targetField": "remark",
    })

    resp = await client.post("/api/rules/reset-default")
    assert resp.status_code == 200
    data = resp.json()
    custom = [r for r in data["columnMappingRules"] if "自定义" in r.get("sourceKeywords", [])]
    assert len(custom) == 0
    assert len(data["columnMappingRules"]) >= 9


# ── POST /api/rules/test ──


@pytest.mark.anyio
async def test_test_rule_match(client: AsyncClient) -> None:
    # Add a rule
    await client.put("/api/rules", json={
        "type": "column_mapping",
        "sourceKeywords": ["单价", "报价"],
        "targetField": "unit_price",
    })
    resp = await client.post("/api/rules/test", json={"columnName": "单价"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert data["targetField"] == "unit_price"


@pytest.mark.anyio
async def test_test_rule_no_match(client: AsyncClient) -> None:
    resp = await client.post("/api/rules/test", json={"columnName": "不存在的列名"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is False
