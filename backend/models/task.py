from enum import Enum
from typing import Any

from pydantic import BaseModel


class TaskStatusEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    task_id: str
    task_type: str
    status: TaskStatusEnum
    progress: float  # 0.0 - 1.0
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: Any | None = None
