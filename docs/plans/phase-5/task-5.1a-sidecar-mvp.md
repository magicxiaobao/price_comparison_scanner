# Task 5.1a: Sidecar 最小可用版本（启动/端口/token/退出清理）

> **拆分说明：** 原 Task 5.1 拆分为 5.1a（MVP）和 5.1b（Hardening）。5.1a 聚焦"能启动、能连接、能退出"，是 Phase 5 后续任务的基座。心跳、自动重启、安全模式、孤儿进程强化清理移至 5.1b。

## 输入条件

- Phase 4 全部完成，所有业务 API 可用
- `frontend/src-tauri/src/main.rs` 存在（Phase 0 创建的默认 Tauri 入口）
- `frontend/src-tauri/tauri.conf.json` 已配置 `externalBin` 和 CSP（Phase 0 配置）
- 后端 `GET /api/health` 已可用
- 后端 `backend/main.py` 支持 `--host`、`--port`、`--token` 命令行参数

## 输出物

- 修改: `frontend/src-tauri/src/main.rs`（填充 sidecar MVP 启动逻辑）
- 修改: `frontend/src-tauri/src/lib.rs`（如果启动逻辑在此文件中）
- 修改: `frontend/src/lib/api.ts`（新增 `initApiConnection()` — Tauri/开发模式判断 + invoke 调用）
- 修改: `frontend/src/main.tsx`（渲染前调用 `initApiConnection()`，接入启动初始化链路）
- 创建: `backend/api/shutdown.py`（`POST /api/shutdown` 路由）
- 创建: `backend/tests/test_shutdown.py`（shutdown API 回归测试）
- 修改: `backend/main.py`（注册 shutdown 路由）
- 修改: `docs/api/openapi.json`（新增 shutdown 端点）

## 禁止修改

- 不修改 `backend/engines/` 目录
- 不修改 `backend/services/` 目录
- 不修改 `frontend/src/app/`、`frontend/src/components/`、`frontend/src/stores/` 下的 React 组件和 Store
- 不修改 `backend/db/` 目录

> 注意：`frontend/src/main.tsx` 和 `frontend/src/lib/api.ts` 允许修改（它们不属于上述禁止目录）。

## 本 Task 的范围（5.1a-MVP）

### 包含

1. **端口扫描**：从 17396 开始，尝试 10 个端口（17396-17405），找到第一个可用端口
2. **Session token 生成**：UUID v4
3. **Sidecar 启动**：通过 Tauri shell API 启动 backend sidecar，传递 `--host 127.0.0.1 --port {port} --token {token}`
4. **PID 文件写入**：写入 `app_data_dir/.sidecar.pid`
5. **启动就绪等待**：轮询 `GET /api/health`，每 500ms 一次，超时 10 秒
6. **退出清理**：应用关闭时发送 `POST /api/shutdown` → 等待 3 秒 → 强制 kill → 删除 PID 文件
7. **`get_sidecar_info` invoke 命令**：暴露 port、token 给前端
8. **前端 API Client 适配**：`api.ts` 新增 `initApiConnection()` 统一初始化函数
9. **前端启动接线**：`main.tsx` 在 `ReactDOM.createRoot` 前调用 `initApiConnection()`，确保渲染时后端连接已就绪
10. **`POST /api/shutdown` 后端路由**
11. **`test_shutdown.py` 回归测试**
12. **启动失败基础提示**：如果 sidecar 启动超时或 invoke 失败，在 Rust 端 log 错误并让前端显示连接失败状态

### 不包含（移至 5.1b）

- 心跳循环（5 秒间隔持续健康检查）
- 自动重启（连续失败后 kill + 重新启动）
- 重启频率追踪（1 分钟内重启次数限制）
- 安全模式（连续崩溃后进入安全模式 + 前端弹窗）
- 孤儿进程强化清理（启动时检测旧 PID 文件并清理残留进程）
- `sidecar-safe-mode` / `sidecar-restarted` 前端事件

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

### Tauri Rust 端：sidecar MVP 逻辑

> **必须用 DeepWiki 查询 `tauri-apps/tauri`**，确认 Tauri 2.x 的 sidecar 启动 API（`Command::new_sidecar`）、进程管理 API、`invoke` 机制的最新用法。以下为逻辑伪代码，实际实现需根据 Tauri 2.x API 调整。

#### 核心数据结构（MVP 版）

```rust
struct SidecarState {
    port: u16,
    token: String,
    pid: Option<u32>,
    child: Option<CommandChild>,
}
```

> 注意：不包含 `restart_count`、`restart_window_start`、`safe_mode` 字段，这些属于 5.1b。

#### 启动流程（MVP 伪代码）

```
fn start_sidecar(app_handle) -> Result<SidecarState>:
    // 1. 生成 session token
    token = uuid::Uuid::new_v4().to_string()

    // 2. 扫描可用端口
    port = 17396
    for attempt in 0..10:
        if port_available(port + attempt):
            port = port + attempt
            break
        if attempt == 9:
            return Err("所有端口 17396-17405 均被占用")

    // 3. 启动 sidecar
    child = app_handle.shell().sidecar("backend")
        .args(["--host", "127.0.0.1", "--port", &port.to_string(), "--token", &token])
        .spawn()?

    // 4. 写入 PID 文件
    pid_path = app_data_dir / ".sidecar.pid"
    write(pid_path, child.pid().to_string())

    // 5. 等待 sidecar 就绪（轮询 health，超时 10 秒）
    for _ in 0..20:
        sleep(500ms)
        response = http_get(
            "http://127.0.0.1:{port}/api/health",
            header: "Authorization: Bearer {token}"
        )
        if response.ok():
            return Ok(SidecarState { port, token, pid, child })
    return Err("Sidecar 启动超时（10 秒内未响应 health API）")
```

#### 退出清理（MVP 伪代码）

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

#### Tauri invoke 命令

```rust
#[tauri::command]
fn get_sidecar_info(state: State<SidecarState>) -> SidecarInfo {
    SidecarInfo {
        port: state.port,
        token: state.token.clone(),
    }
}
```

> MVP 版不暴露 `safe_mode` 字段（5.1b 加入）。

#### 前端启动初始化（关键接线点）

##### 1. `src/lib/api.ts` — 新增 `initApiConnection()`

```typescript
import { invoke } from '@tauri-apps/api/core';

interface SidecarInfo {
  port: number;
  token: string;
}

/**
 * 统一 API 连接初始化。
 * - Tauri 模式：通过 invoke 从 Rust 端获取 sidecar 的 port 和 token
 * - 开发模式：保持现有逻辑（Vite proxy + VITE_DEV_TOKEN 环境变量）
 *
 * 必须在 React 渲染前调用，否则前端所有 API 请求都会失败。
 */
export async function initApiConnection(): Promise<void> {
  if (window.__TAURI_INTERNALS__) {
    // Tauri 生产模式
    const info = await invoke<SidecarInfo>('get_sidecar_info');
    configureTauriConnection(info.port, info.token);
  }
  // 开发模式：已在模块顶层通过 VITE_DEV_TOKEN 设置，无需额外操作
}
```

> **环境判断**：使用 `window.__TAURI_INTERNALS__` 检测是否运行在 Tauri 环境中。这是 Tauri 2.x 注入的全局对象，开发模式下（纯 Vite）不存在。必须用 DeepWiki 确认 Tauri 2.x 的最新环境检测方式，如果 API 有变化则相应调整。

##### 2. `src/main.tsx` — 调用初始化

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initApiConnection } from "./lib/api";
import "./styles/globals.css";

// 初始化 API 连接后再渲染
initApiConnection()
  .then(() => {
    ReactDOM.createRoot(document.getElementById("root")!).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  })
  .catch((err) => {
    // 初始化失败：显示基础错误信息（不依赖 React 组件）
    const root = document.getElementById("root");
    if (root) {
      root.innerHTML = `
        <div style="padding:48px;text-align:center;font-family:system-ui">
          <h2>后端服务连接失败</h2>
          <p style="color:#666">无法连接到后端 sidecar 服务，请重启应用。</p>
          <p style="color:#999;font-size:12px">${String(err)}</p>
        </div>
      `;
    }
  });
```

> **关键设计**：`initApiConnection()` 在 `ReactDOM.createRoot` 之前 await，确保渲染开始时 axios client 的 baseURL 和 Authorization header 已设置。如果初始化失败（sidecar 未启动、invoke 异常），不渲染 React 树，直接在 DOM 上显示纯 HTML 错误页，避免连锁 API 报错。

##### 3. 初始化时序

```
应用启动
  ├── [Tauri 模式]
  │   Rust start_sidecar() → 等待 health ready
  │   → 前端加载 → main.tsx → initApiConnection()
  │   → invoke('get_sidecar_info') → 获取 port/token
  │   → configureTauriConnection() → 设置 axios
  │   → ReactDOM.render()
  │
  └── [开发模式]
      Vite dev server 启动 → 前端加载 → main.tsx → initApiConnection()
      → window.__TAURI_INTERNALS__ 不存在 → 跳过 invoke
      → VITE_DEV_TOKEN 已在模块顶层设置 → 直接 render
```

### tauri.conf.json 确认项

验证以下配置已正确设置（Phase 0 应已配置）：
- `bundle.externalBin` 包含 `"binaries/backend"`
- `app.security.csp` 的 `connect-src` 覆盖 `http://127.0.0.1:17396` 至 `http://127.0.0.1:17405`

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
3. 正常关闭应用 → 验证 sidecar 进程消失 + PID 文件被删除
4. 占用 17396 端口 → 启动应用 → 验证自动使用 17397
5. 前端页面可正常加载并调用后端 API（如新建项目）
```

> 手动重启、安全模式、孤儿清理的验证在 5.1b 中执行。

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
git add backend/api/shutdown.py backend/tests/test_shutdown.py backend/main.py \
  frontend/src-tauri/src/main.rs frontend/src-tauri/src/lib.rs \
  frontend/src/main.tsx frontend/src/lib/api.ts \
  docs/api/openapi.json
git commit -m "Phase 5.1a: Sidecar MVP（启动/端口扫描/token/退出清理/前端初始化）+ shutdown API"
```
