# Task 5.1: Tauri Sidecar 集成（启动/监控/重启/端口/token/清理）

## 输入条件

- Phase 4 全部完成，所有业务 API 可用
- `frontend/src-tauri/src/main.rs` 存在（Phase 0 创建的默认 Tauri 入口）
- `frontend/src-tauri/tauri.conf.json` 已配置 `externalBin` 和 CSP（Phase 0 配置）
- 后端 `GET /api/health` 已可用
- 后端 `backend/main.py` 支持 `--host`、`--port`、`--token` 命令行参数

## 输出物

- 修改: `frontend/src-tauri/src/main.rs`（填充 sidecar 管理全部逻辑）
- 修改: `frontend/src/lib/api.ts`（启动时通过 Tauri invoke 获取 port 和 token，替代开发模式硬编码）
- 创建: `backend/api/shutdown.py`（`POST /api/shutdown` 路由）
- 修改: `backend/main.py`（注册 shutdown 路由）
- 修改: `docs/api/openapi.json`（新增 shutdown 端点）

## 禁止修改

- 不修改 `backend/engines/` 目录
- 不修改 `backend/services/` 目录
- 不修改 `frontend/src/app/`、`frontend/src/components/`、`frontend/src/stores/` 下的 React 组件和 Store（前端 UI 变更由 Task 5.2 负责）
- 不修改 `backend/db/` 目录

## 实现规格

### 后端：POST /api/shutdown

```python
# backend/api/shutdown.py
from fastapi import APIRouter

router = APIRouter(tags=["系统"])

@router.post("/shutdown")
async def shutdown():
    """优雅关闭 sidecar 进程。Tauri 退出时调用。"""
    import asyncio
    import os
    import signal

    async def _shutdown():
        await asyncio.sleep(0.5)  # 给响应返回的时间
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_shutdown())
    return {"status": "shutting_down"}
```

注册路由（在 `main.py` 中添加）：
```python
from api.shutdown import router as shutdown_router
app.include_router(shutdown_router, prefix="/api")
```

### Tauri Rust 端：main.rs sidecar 管理

> **必须用 DeepWiki 查询 `tauri-apps/tauri`**，确认 Tauri 2.x 的 sidecar 启动 API（`Command::new_sidecar`）、进程管理 API、`invoke` 机制的最新用法。若 DeepWiki 不可用，以 Tauri 官方文档（https://v2.tauri.app/）或项目内已有 Tauri 配置为准。以下为逻辑伪代码，实际实现需根据 Tauri 2.x API 调整。

#### 核心数据结构

```rust
// 伪代码：sidecar 管理状态
struct SidecarState {
    port: u16,
    token: String,
    pid: Option<u32>,
    child: Option<CommandChild>,        // Tauri sidecar 子进程句柄
    restart_count: u32,                  // 当前分钟内重启次数
    restart_window_start: Instant,       // 重启计数窗口起始时间
    safe_mode: bool,                     // 安全模式标记
}
```

#### 启动流程（伪代码）

```
fn start_sidecar(app_handle) -> Result<SidecarState>:
    // 1. 清理孤儿进程
    pid_path = app_data_dir / ".sidecar.pid"
    if pid_path.exists():
        old_pid = read(pid_path)
        if process_exists(old_pid):
            kill(old_pid, SIGTERM)
            wait(1 second)
            if process_exists(old_pid):
                kill(old_pid, SIGKILL)
        delete(pid_path)

    // 2. 生成 session token
    token = uuid::Uuid::new_v4().to_string()

    // 3. 扫描可用端口
    port = 17396
    for attempt in 0..10:
        if port_available(port + attempt):
            port = port + attempt
            break
        if attempt == 9:
            return Err("所有端口 17396-17406 均被占用")

    // 4. 启动 sidecar
    //    使用 Tauri 2.x API: app_handle.shell().sidecar("backend")
    //    传递参数: --host 127.0.0.1 --port {port} --token {token}
    child = app_handle.shell().sidecar("backend")
        .args(["--host", "127.0.0.1", "--port", &port.to_string(), "--token", &token])
        .spawn()?

    // 5. 写入 PID 文件
    write(pid_path, child.pid().to_string())

    // 6. 等待 sidecar 就绪（轮询 health，超时 10 秒）
    for _ in 0..20:   // 每 500ms 轮询一次，最多 20 次 = 10 秒
        sleep(500ms)
        response = http_get(
            "http://127.0.0.1:{port}/api/health",
            header: "Authorization: Bearer {token}"
        )
        if response.ok():
            return Ok(SidecarState { port, token, pid, child, ... })
    return Err("Sidecar 启动超时")
```

#### 健康检查（伪代码）

```
fn health_check_loop(state: SidecarState):
    consecutive_failures = 0

    loop every 5 seconds:
        response = http_get(
            "http://127.0.0.1:{state.port}/api/health",
            header: "Authorization: Bearer {state.token}",
            timeout: 3 seconds
        )

        if response.ok():
            consecutive_failures = 0
            continue

        consecutive_failures += 1

        if consecutive_failures >= 3:   // 15 秒无响应
            // 检查重启频率
            if state.restart_window 超过 1 分钟:
                state.restart_count = 0
                state.restart_window_start = now()

            if state.restart_count >= 3:
                // 进入安全模式
                state.safe_mode = true
                emit_event("sidecar-safe-mode")  // 通知前端弹窗
                break

            // 自动重启
            state.restart_count += 1
            kill_sidecar(state)

            // 尝试原端口，不可用则重新扫描
            if !port_available(state.port):
                state.port = scan_available_port()

            start_sidecar(state)  // 复用 token
            consecutive_failures = 0

            // 通知前端新端口（如果变了）
            emit_event("sidecar-restarted", { port: state.port })
```

#### 退出清理（伪代码）

```
fn on_app_exit(state: SidecarState):
    // 1. 发送 POST /api/shutdown
    http_post(
        "http://127.0.0.1:{state.port}/api/shutdown",
        header: "Authorization: Bearer {state.token}"
    )

    // 2. 等待 3 秒
    sleep(3 seconds)

    // 3. 若进程仍存在，强制 kill
    if let Some(child) = state.child:
        child.kill()

    // 4. 删除 PID 文件
    delete(app_data_dir / ".sidecar.pid")
```

#### Tauri invoke 命令（暴露给前端）

```rust
// 前端通过 invoke 获取连接信息
#[tauri::command]
fn get_sidecar_info(state: State<SidecarState>) -> SidecarInfo {
    SidecarInfo {
        port: state.port,
        token: state.token.clone(),
        safe_mode: state.safe_mode,
    }
}
```

#### 前端 API Client 适配

前端 `src/lib/api.ts` 需在应用启动时通过 Tauri invoke 获取 `port` 和 `token`，替代开发模式下的硬编码/环境变量。

```typescript
// 生产模式下（Tauri 环境）
import { invoke } from '@tauri-apps/api/core';

interface SidecarInfo {
  port: number;
  token: string;
  safe_mode: boolean;
}

async function getSidecarInfo(): Promise<SidecarInfo> {
  return await invoke('get_sidecar_info');
}
```

开发模式下保持现有逻辑不变（Vite proxy + 环境变量 token）。

### tauri.conf.json 确认项

确认以下配置已正确设置（Phase 0 应已配置，此处仅验证）：

```json
{
  "bundle": {
    "externalBin": ["binaries/backend"]
  },
  "app": {
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://localhost:17396 http://localhost:17397 http://localhost:17398 http://localhost:17399 http://localhost:17400 http://localhost:17401 http://localhost:17402 http://localhost:17403 http://localhost:17404 http://localhost:17405 http://localhost:17406"
    }
  }
}
```

## 测试与验收

### 后端测试

```bash
cd backend

# 门禁
ruff check .
mypy . --ignore-missing-imports
pytest -x -q

# shutdown API 测试
pytest tests/test_shutdown.py -v
```

**test_shutdown.py 断言：**
- `POST /api/shutdown` → 200，响应 `{"status": "shutting_down"}`
- shutdown 端点需要认证（无 token → 403）

### Sidecar 集成测试（手动验证）

```
1. 启动 `pnpm tauri dev`
2. 验证 sidecar 自动启动并响应 health API
3. 手动 kill sidecar 进程 → 验证自动重启
4. 连续快速 kill 4 次 → 验证进入安全模式 + 弹窗提示
5. 正常关闭应用 → 验证 PID 文件被删除
6. 模拟异常退出（强制关闭应用）→ 重新启动 → 验证孤儿进程被清理
7. 占用 17396 端口 → 启动应用 → 验证自动使用 17397
```

### 前端门禁

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
```

### 契约更新

```bash
cd backend
python scripts/generate_openapi.py
# 确认 openapi.json 包含 POST /api/shutdown
```

## 提交

```bash
git add backend/api/shutdown.py backend/main.py frontend/src-tauri/src/main.rs docs/api/openapi.json
git commit -m "Phase 5.1: Tauri Sidecar 集成（启动/心跳/重启/安全模式/退出清理）+ shutdown API"
```
