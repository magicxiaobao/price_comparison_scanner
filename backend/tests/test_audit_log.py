"""Task 2.1: AuditLogService 单元测试"""
import time
import uuid

import pytest

from db.database import Database
from services.audit_log_service import AuditLogService


@pytest.fixture
def db(tmp_path):  # type: ignore[no-untyped-def]
    return Database(tmp_path / "test.db")


@pytest.fixture
def audit_service(db: Database) -> AuditLogService:
    return AuditLogService(db)


@pytest.fixture
def project_id(db: Database) -> str:
    """创建测试项目"""
    from datetime import UTC, datetime

    pid = "p-test"
    now = datetime.now(UTC).isoformat()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (pid, "测试项目", now, now),
        )
    return pid


def test_log_modify_field(audit_service: AuditLogService, project_id: str) -> None:
    log_id = audit_service.log(
        project_id=project_id,
        action_type="modify_field",
        action_source="user",
        target_table="standardized_rows",
        target_id="row-1",
        field_name="unit_price",
        before_value="100.5",
        after_value="120.0",
    )
    assert log_id
    logs = audit_service.get_project_logs(project_id)
    assert len(logs) == 1
    log = logs[0]
    assert log["action_type"] == "modify_field"
    assert log["action_source"] == "user"
    assert log["target_table"] == "standardized_rows"
    assert log["target_id"] == "row-1"
    assert log["field_name"] == "unit_price"
    assert log["before_value"] == "100.5"
    assert log["after_value"] == "120.0"


def test_log_standardize(audit_service: AuditLogService, project_id: str) -> None:
    log_id = audit_service.log(
        project_id=project_id,
        action_type="standardize",
        action_source="system",
    )
    assert log_id
    logs = audit_service.get_project_logs(project_id)
    assert logs[0]["action_type"] == "standardize"
    assert logs[0]["action_source"] == "system"


def test_log_import(audit_service: AuditLogService, project_id: str) -> None:
    log_id = audit_service.log(
        project_id=project_id,
        action_type="import",
        action_source="import",
        target_table="supplier_files",
        target_id="f-1",
    )
    assert log_id
    logs = audit_service.get_project_logs(project_id)
    assert logs[0]["action_source"] == "import"


def test_get_project_logs_descending(
    audit_service: AuditLogService, project_id: str
) -> None:
    audit_service.log(project_id=project_id, action_type="import")
    time.sleep(0.01)
    audit_service.log(project_id=project_id, action_type="standardize")
    time.sleep(0.01)
    audit_service.log(project_id=project_id, action_type="modify_field")
    logs = audit_service.get_project_logs(project_id)
    assert len(logs) == 3
    assert logs[0]["action_type"] == "modify_field"
    assert logs[1]["action_type"] == "standardize"
    assert logs[2]["action_type"] == "import"


def test_get_target_logs(audit_service: AuditLogService, project_id: str) -> None:
    target = "row-42"
    audit_service.log(
        project_id=project_id,
        action_type="modify_field",
        target_id=target,
        field_name="unit_price",
        before_value="10",
        after_value="20",
    )
    audit_service.log(
        project_id=project_id,
        action_type="modify_field",
        target_id=target,
        field_name="quantity",
        before_value="5",
        after_value="10",
    )
    logs = audit_service.get_target_logs(target)
    assert len(logs) == 2


def test_before_after_value_as_string(
    audit_service: AuditLogService, project_id: str
) -> None:
    """数值类型应转为字符串存储"""
    audit_service.log(
        project_id=project_id,
        action_type="modify_field",
        before_value="99.9",
        after_value="199.9",
    )
    logs = audit_service.get_project_logs(project_id)
    assert isinstance(logs[0]["before_value"], str)
    assert isinstance(logs[0]["after_value"], str)


def test_log_returns_log_id(audit_service: AuditLogService, project_id: str) -> None:
    log_id = audit_service.log(
        project_id=project_id, action_type="export"
    )
    assert log_id
    # 验证是有效 UUID
    parsed = uuid.UUID(log_id)
    assert str(parsed) == log_id


def test_created_at_is_iso8601(
    audit_service: AuditLogService, project_id: str
) -> None:
    audit_service.log(project_id=project_id, action_type="import")
    logs = audit_service.get_project_logs(project_id)
    ts = logs[0]["created_at"]
    assert "T" in ts  # ISO 8601 基本验证
