# Task 1.1: TaskManager 异步任务框架 + 任务状态 API

## 输入条件

- Phase 0 全部完成（后端骨架、数据库层、项目 CRUD 就绪）

## 输出物

- 创建: `backend/engines/task_manager.py`
- 创建: `backend/api/tasks.py`
- 修改: `backend/main.py`（注册 tasks 路由）
- 创建: `backend/tests/test_task_manager.py`
- 创建: `backend/tests/test_task_api.py`

## 禁止修改

- 不修改 `backend/db/database.py`
- 不修改 `backend/db/schema.sql`
- 不修改 `backend/api/middleware.py`
- 不修改 `frontend/`

## 实现规格

### engines/task_manager.py

TaskManager 是一个全局单例，使用 `ThreadPoolExecutor` 作为执行后端。任务状态存储在内存中（进程重启后丢失，MVP 可接受）。

```python
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum
from typing import Any, Callable
from datetime import datetime, timezone


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo:
    """内部任务状态记录"""
    task_id: str
    task_type: str
    status: TaskStatus
    progress: float          # 0.0 - 1.0
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

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskInfo] = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()

    def submit(self, task_type: str, fn: Callable, *args: Any, **kwargs: Any) -> str:
        """
        提交任务，返回 task_id。
        fn 接收一个额外的 progress_callback(float) 参数作为第一个参数，
        用于报告进度（0.0 - 1.0）。
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

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
                self._tasks[task_id].started_at = datetime.now(timezone.utc).isoformat()
            try:
                result = fn(progress_callback, *args, **kwargs)
                with self._lock:
                    self._tasks[task_id].status = TaskStatus.COMPLETED
                    self._tasks[task_id].progress = 1.0
                    self._tasks[task_id].result = result
                    self._tasks[task_id].completed_at = datetime.now(timezone.utc).isoformat()
                return result
            except Exception as e:
                with self._lock:
                    self._tasks[task_id].status = TaskStatus.FAILED
                    self._tasks[task_id].error = str(e)
                    self._tasks[task_id].completed_at = datetime.now(timezone.utc).isoformat()
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
                info.completed_at = datetime.now(timezone.utc).isoformat()
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
    global _task_manager
    if _task_manager is None:
        with _tm_lock:
            if _task_manager is None:
                _task_manager = TaskManager()
    return _task_manager
```

**设计要点：**
- `submit()` 的 `fn` 必须接受 `progress_callback` 作为第一个参数
- 任务状态存储在内存字典中，用 `threading.Lock` 保护
- 全局单例通过 `get_task_manager()` 访问
- `cancel()` 只能取消 queued 状态的任务（ThreadPoolExecutor 限制，running 中的任务无法强制取消）

### api/tasks.py

```python
from fastapi import APIRouter, HTTPException

from engines.task_manager import get_task_manager

router = APIRouter(tags=["异步任务"])


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    tm = get_task_manager()
    info = tm.get_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": info.task_id,
        "task_type": info.task_type,
        "status": info.status.value,
        "progress": info.progress,
        "error": info.error,
        "created_at": info.created_at,
        "started_at": info.started_at,
        "completed_at": info.completed_at,
    }


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    tm = get_task_manager()
    info = tm.get_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")
    cancelled = tm.cancel(task_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="任务无法取消（可能已在运行中）")
    return {"detail": "任务已取消"}
```

### main.py 修改

添加 tasks 路由：

```python
from api.tasks import router as tasks_router
app.include_router(tasks_router, prefix="/api")
```

## 测试与验收

### tests/test_task_manager.py

```python
import time
import pytest
from engines.task_manager import TaskManager, TaskStatus


@pytest.fixture
def tm():
    manager = TaskManager(max_workers=2)
    yield manager
    manager.shutdown()


def test_submit_and_complete(tm):
    """提交任务并等待完成"""
    def my_task(progress_callback):
        progress_callback(0.5)
        time.sleep(0.1)
        progress_callback(1.0)
        return {"result": "done"}

    task_id = tm.submit("test", my_task)
    assert task_id is not None

    # 等待完成
    for _ in range(50):
        info = tm.get_status(task_id)
        if info and info.status == TaskStatus.COMPLETED:
            break
        time.sleep(0.1)

    info = tm.get_status(task_id)
    assert info.status == TaskStatus.COMPLETED
    assert info.progress == 1.0
    assert tm.get_result(task_id) == {"result": "done"}


def test_submit_with_failure(tm):
    """任务抛出异常 → 状态为 failed"""
    def failing_task(progress_callback):
        raise ValueError("模拟失败")

    task_id = tm.submit("test", failing_task)

    for _ in range(50):
        info = tm.get_status(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = tm.get_status(task_id)
    assert info.status == TaskStatus.FAILED
    assert "模拟失败" in info.error


def test_get_status_nonexistent(tm):
    """查询不存在的任务 → None"""
    assert tm.get_status("nonexistent") is None


def test_progress_callback(tm):
    """进度回调正确更新"""
    def task_with_progress(progress_callback):
        progress_callback(0.3)
        time.sleep(0.2)
        progress_callback(0.7)
        time.sleep(0.1)
        return "ok"

    task_id = tm.submit("test", task_with_progress)
    time.sleep(0.1)
    progress = tm.get_progress(task_id)
    assert progress is not None
    assert 0.0 <= progress <= 1.0


def test_cancel_queued_task(tm):
    """取消排队中的任务"""
    # 先占满线程池
    def blocking_task(progress_callback):
        time.sleep(5)

    tm.submit("block", blocking_task)
    tm.submit("block", blocking_task)

    # 第三个任务应该在队列中
    task_id = tm.submit("test", lambda cb: "result")
    cancelled = tm.cancel(task_id)
    # 注意：取消不一定成功（取决于线程池调度），只要 API 不崩溃即可
    if cancelled:
        info = tm.get_status(task_id)
        assert info.status == TaskStatus.CANCELLED


def test_get_result_incomplete(tm):
    """未完成任务获取结果 → None"""
    def slow_task(progress_callback):
        time.sleep(10)

    task_id = tm.submit("test", slow_task)
    assert tm.get_result(task_id) is None
```

### tests/test_task_api.py

```python
import time
import pytest


@pytest.fixture(autouse=True)
def _use_temp_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEV_MODE", "1")
    from config import Settings
    import config
    config.settings = Settings()


@pytest.fixture
async def client():
    from main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_get_task_status_not_found(client):
    resp = await client.get("/api/tasks/nonexistent-id/status")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_cancel_task_not_found(client):
    resp = await client.delete("/api/tasks/nonexistent-id")
    assert resp.status_code == 404
```

### 门禁检查

```bash
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest tests/test_task_manager.py tests/test_task_api.py -x -q
```

**断言清单：**
- `TaskManager.submit()` → 返回非空 task_id 字符串
- 任务完成后 `get_status()` → status == "completed"，progress == 1.0
- 任务失败后 `get_status()` → status == "failed"，error 包含异常信息
- `get_status("nonexistent")` → None
- `get_progress()` 返回 0.0-1.0 范围内的值
- `get_result()` 未完成时返回 None，完成后返回正确结果
- `GET /api/tasks/{id}/status` 不存在 → 404
- `DELETE /api/tasks/{id}` 不存在 → 404

## 提交

```bash
git add backend/engines/task_manager.py backend/api/tasks.py \
       backend/main.py backend/tests/test_task_manager.py \
       backend/tests/test_task_api.py
git commit -m "Phase 1.1: TaskManager 异步任务框架 + 任务状态 API（ThreadPoolExecutor 实现）"
```
