# Task 5.1b: Sidecar 加固（心跳/自动重启/安全模式/孤儿清理）

> **拆分说明：** 原 Task 5.1 的第二层。依赖 5.1a-MVP 完成。是否在 5.4 E2E 联调前实现取决于 5.1a 的稳定性评估——如果 E2E 过程中 sidecar 不稳定，则前置实现；否则可后置到 5.4 之后。

## 输入条件

- Task 5.1a 完成：sidecar 可正常启动、连接、退出
- `frontend/src-tauri/src/main.rs`（或 `lib.rs`）已有 MVP sidecar 管理逻辑
- `SidecarState` 结构体已定义（MVP 字段）

## 输出物

- 修改: `frontend/src-tauri/src/main.rs`（或 `lib.rs`）— 扩展 sidecar 管理逻辑
- 修改: `frontend/src/lib/api.ts`（监听 `sidecar-restarted` 事件，更新连接信息）
- 可选修改: `frontend/src/components/` — 安全模式弹窗组件（如果需要新组件）

## 禁止修改

- 不修改 `backend/` 目录（5.1b 纯 Rust + 前端侧）
- 不修改 `backend/engines/`、`backend/services/`、`backend/db/`
- 不修改已有阶段组件内部逻辑

## 本 Task 的范围（5.1b-Hardening）

### 包含

1. **孤儿进程清理**：启动时检测旧 PID 文件，若残留进程存在则 SIGTERM → 等待 1 秒 → SIGKILL → 删除 PID 文件
2. **心跳循环**：每 5 秒轮询 `GET /api/health`（3 秒超时）
3. **自动重启**：连续 3 次心跳失败（15 秒无响应）→ kill 旧进程 → 重新启动 sidecar
4. **重启频率追踪**：1 分钟窗口内最多重启 3 次
5. **安全模式**：超过重启次数上限 → 设置 `safe_mode = true` → 发送 `sidecar-safe-mode` 事件通知前端
6. **端口重扫描**：重启时如果原端口不可用，重新扫描可用端口
7. **前端事件监听**：`sidecar-restarted`（端口可能变化）、`sidecar-safe-mode`（弹窗提示用户）
8. **`get_sidecar_info` 扩展**：返回 `safe_mode` 字段

### SidecarState 扩展字段

```rust
struct SidecarState {
    // --- MVP 字段（5.1a 已有）---
    port: u16,
    token: String,
    pid: Option<u32>,
    child: Option<CommandChild>,

    // --- Hardening 新增 ---
    restart_count: u32,                  // 当前窗口内重启次数
    restart_window_start: Instant,       // 重启计数窗口起始时间
    safe_mode: bool,                     // 安全模式标记
}
```

## 实现规格

### 孤儿进程清理（插入启动流程最前端）

```
fn cleanup_orphan(app_data_dir):
    pid_path = app_data_dir / ".sidecar.pid"
    if !pid_path.exists():
        return

    old_pid = read(pid_path)
    if process_exists(old_pid):
        kill(old_pid, SIGTERM)
        sleep(1 second)
        if process_exists(old_pid):
            kill(old_pid, SIGKILL)
    delete(pid_path)
```

> 在 5.1a 的 `start_sidecar()` 最前面插入此调用。

### 心跳循环

```
fn health_check_loop(state: Arc<Mutex<SidecarState>>):
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

        if consecutive_failures >= 3:
            // 检查重启频率窗口
            if elapsed(state.restart_window_start) > 60 seconds:
                state.restart_count = 0
                state.restart_window_start = now()

            if state.restart_count >= 3:
                state.safe_mode = true
                emit_event("sidecar-safe-mode")
                break  // 停止心跳循环

            // 自动重启
            state.restart_count += 1
            kill_sidecar(state)

            if !port_available(state.port):
                state.port = scan_available_port()

            start_sidecar(state)  // 复用 token
            consecutive_failures = 0

            emit_event("sidecar-restarted", { port: state.port })
```

### 前端事件监听

```typescript
// src/lib/api.ts 或独立模块
import { listen } from '@tauri-apps/api/event';

// 监听 sidecar 重启（端口可能变化）
await listen<{ port: number }>('sidecar-restarted', (event) => {
  configureTauriConnection(event.payload.port, currentToken);
});

// 监听安全模式（弹窗提示用户）
await listen('sidecar-safe-mode', () => {
  // 显示对话框：后端服务多次启动失败，请重启应用或联系技术支持
});
```

### get_sidecar_info 扩展

```rust
#[tauri::command]
fn get_sidecar_info(state: State<SidecarState>) -> SidecarInfo {
    SidecarInfo {
        port: state.port,
        token: state.token.clone(),
        safe_mode: state.safe_mode,  // 5.1b 新增
    }
}
```

## 测试与验收

### Sidecar 集成测试（手动验证）

```
1. 启动应用 → 手动 kill sidecar 进程 → 验证自动重启（约 15 秒后恢复）
2. 重启后前端 API 调用恢复正常
3. 连续快速 kill 4 次（1 分钟内）→ 验证进入安全模式
4. 安全模式下前端弹窗提示用户
5. 模拟异常退出（强制关闭应用）→ 重新启动 → 验证孤儿进程被清理
6. 启动应用 → 验证 PID 文件包含正确 PID
```

### 前端门禁

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
```

## 提交

```bash
git add frontend/src-tauri/src/main.rs frontend/src-tauri/src/lib.rs frontend/src/lib/api.ts
git commit -m "Phase 5.1b: Sidecar 加固（心跳/自动重启/安全模式/孤儿清理）"
```
