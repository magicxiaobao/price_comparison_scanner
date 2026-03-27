import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo:
    """内部任务状态记录。"""

    task_id: str
    task_type: str
    status: TaskStatus
    progress: float  # 0.0 - 1.0
    result: Any
    error: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None


class TaskManager:
    """
    异步任务管理器。MVP 使用 ThreadPoolExecutor 实现。
    全局单例，通过 get_task_manager() 获取。
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskInfo] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()

    def submit(self, task_type: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """
        提交任务，返回 task_id。
        fn 接收一个额外的 progress_callback(float) 参数作为第一个参数，
        用于报告进度（0.0 - 1.0）。
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        info = TaskInfo()
        info.task_id = task_id
        info.task_type = task_type
        info.status = TaskStatus.QUEUED
        info.progress = 0.0
        info.result = None
        info.error = None
        info.created_at = now
        info.started_at = None
        info.completed_at = None

        def progress_callback(progress: float) -> None:
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].progress = min(max(progress, 0.0), 1.0)

        def wrapper() -> Any:
            with self._lock:
                self._tasks[task_id].status = TaskStatus.RUNNING
                self._tasks[task_id].started_at = datetime.now(UTC).isoformat()
            try:
                result = fn(progress_callback, *args, **kwargs)
                with self._lock:
                    self._tasks[task_id].status = TaskStatus.COMPLETED
                    self._tasks[task_id].progress = 1.0
                    self._tasks[task_id].result = result
                    self._tasks[task_id].completed_at = datetime.now(UTC).isoformat()
                return result
            except Exception as e:
                with self._lock:
                    self._tasks[task_id].status = TaskStatus.FAILED
                    self._tasks[task_id].error = str(e)
                    self._tasks[task_id].completed_at = datetime.now(UTC).isoformat()
                raise

        with self._lock:
            self._tasks[task_id] = info

        future = self._executor.submit(wrapper)
        with self._lock:
            self._futures[task_id] = future

        return task_id

    def get_status(self, task_id: str) -> TaskInfo | None:
        """获取任务状态信息，不存在返回 None"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_progress(self, task_id: str) -> float | None:
        """获取任务进度 0.0-1.0，不存在返回 None"""
        with self._lock:
            info = self._tasks.get(task_id)
            return info.progress if info else None

    def cancel(self, task_id: str) -> bool:
        """取消任务。仅 queued 状态可取消（ThreadPoolExecutor 限制）"""
        with self._lock:
            future = self._futures.get(task_id)
            info = self._tasks.get(task_id)
            if not future or not info:
                return False
            cancelled = future.cancel()
            if cancelled:
                info.status = TaskStatus.CANCELLED
                info.completed_at = datetime.now(UTC).isoformat()
            return cancelled

    def get_result(self, task_id: str) -> Any:
        """获取已完成任务的结果。任务未完成返回 None"""
        with self._lock:
            info = self._tasks.get(task_id)
            if not info or info.status != TaskStatus.COMPLETED:
                return None
            return info.result

    def shutdown(self) -> None:
        """关闭线程池"""
        self._executor.shutdown(wait=False)


# 全局单例
_task_manager: TaskManager | None = None
_tm_lock = threading.Lock()


def get_task_manager() -> TaskManager:
    global _task_manager  # noqa: PLW0603
    if _task_manager is None:
        with _tm_lock:
            if _task_manager is None:
                _task_manager = TaskManager()
    return _task_manager
