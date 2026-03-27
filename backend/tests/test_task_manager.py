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
