# Tauri 2 macOS Sidecar HTTP 请求阻止问题

> 状态：**未解决** | 日期：2026-03-29

## 问题描述

Tauri 2 macOS 桌面应用，前端（React + axios）无法通过 HTTP 请求访问本地 sidecar（FastAPI on 127.0.0.1）。开发模式正常，打包后完全不通。

## 环境

- macOS Darwin 25.3.0 (Apple Silicon arm64)
- Tauri 2.x
- 前端：React + TypeScript + axios
- 后端 sidecar：PyInstaller 打包的 FastAPI（绑定 127.0.0.1:17396）
- 打包：`pnpm tauri build` → DMG

## 现象

1. **开发模式**（`uvicorn + pnpm dev`）一切正常
2. **DMG 安装后**，sidecar 启动成功（Rust 端 health check 通过），但前端 axios 请求**完全不到达后端**
3. access.log 中**零条**来自浏览器（WebView）的请求
4. 用户看到 React 页面（说明 initApiConnection 通过 Tauri IPC invoke 成功），但所有 HTTP API 调用无响应

## 已尝试的方案（均无效）

| 方案 | 结果 |
|------|------|
| FastAPI 添加 CORSMiddleware（allow_origins 含 tauri://localhost 等） | 无效 — 请求根本没到达后端 |
| tauri.conf.json `"csp": null` | 无效 |
| tauri.conf.json `"useHttpsScheme": false` | 无效 |
| 安装 `tauri-plugin-localhost`（前端从 http://localhost:9527 加载） | 无效 |
| CORS middleware 顺序修正（在 SessionTokenMiddleware 外层） | 无效 |
| SessionTokenMiddleware 放行 OPTIONS | 无效 |

## 关键代码

### tauri.conf.json

```json
{
  "app": {
    "windows": [{
      "title": "三方比价支出依据扫描工具",
      "width": 1280,
      "height": 800,
      "useHttpsScheme": false
    }],
    "security": { "csp": null }
  },
  "bundle": {
    "externalBin": ["binaries/backend"]
  }
}
```

### 前端连接逻辑 (api.ts)

```typescript
const client = axios.create({
  baseURL: "",
  headers: { "Content-Type": "application/json" },
});

function configureTauriConnection(port: number, token: string): void {
  client.defaults.baseURL = `http://127.0.0.1:${port}`;
  client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

export async function initApiConnection(): Promise<void> {
  const { isTauri } = await import("@tauri-apps/api/core");
  if (isTauri()) {
    const { invoke } = await import("@tauri-apps/api/core");
    // 重试最多 65 次，等待 sidecar 启动
    for (let i = 0; i < 65; i++) {
      try {
        const info = await invoke<SidecarInfo>("get_sidecar_info");
        configureTauriConnection(info.port, info.token);
        // 注册事件监听...
        return;
      } catch (err) {
        if (String(err).includes("STARTING")) {
          await new Promise(r => setTimeout(r, 1000));
          continue;
        }
        break;
      }
    }
  }
}
```

### Rust sidecar 启动 (lib.rs 关键部分)

```rust
// setup 中异步启动 sidecar
tauri::async_runtime::spawn(async move {
    let result = tokio::task::spawn_blocking(move || start_sidecar(&handle_clone)).await;
    match result {
        Ok(Ok(state)) => { /* 存入 state, 启动 heartbeat */ }
        Ok(Err(e)) => { /* 存储错误 */ }
        Err(join_err) => { /* JoinError */ }
    }
});

// sidecar 通过 tauri-plugin-shell 启动
let (mut rx, child) = app.shell()
    .sidecar("backend")
    .args(["--host", "127.0.0.1", "--port", &port.to_string(), "--token", token])
    .spawn()?;

// health check 用 reqwest（Rust HTTP 客户端，不经过 WebView）
let client = reqwest::Client::builder().timeout(Duration::from_secs(2)).build().unwrap();
// GET http://127.0.0.1:{port}/api/health → 成功
```

### 后端 CORS 配置 (main.py)

```python
app.add_middleware(SessionTokenMiddleware)  # 内层
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
        "http://localhost:1420",
        "http://localhost:5173",
        "http://localhost:9527",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)  # 外层，先执行
```

## 日志

### sidecar.log（启动成功）

```
[1774710635] start_sidecar_with: spawned pid=71842
[1774710635] start_sidecar_with: starting health check (max 60s)
[1774710655] start_sidecar_with: health check passed
[1774710655] start_sidecar: success, pid=71842
```

### access.log（全量请求 — 无前端请求）

```
GET /api/health auth=yes ua=? origin=none          ← Rust heartbeat（正常）
GET /api/tasks//status auth=no ua=curl/8.7.1 origin=none  ← 来源不明
GET /api/tasks//status auth=no ua=curl/8.7.1 origin=none
（零条来自浏览器 WebView 的请求）
```

### error.log

```
Auth rejected: method=GET path=/api/tasks//status
auth_header_present=False server_token_set=True
user_agent=curl/8.7.1
```

## 核心问题

**Tauri IPC（invoke）正常工作，但 WebView 内的 HTTP 请求（axios/XMLHttpRequest）完全不到达 127.0.0.1 的 sidecar 后端。macOS WKWebView 在打包后似乎阻止了所有对 localhost HTTP 的请求。**

## 附加疑问

`GET /api/tasks//status` 带空 task ID、`user_agent=curl/8.7.1` 的请求来源不明 — 不是前端（前端请求根本没到达），不是 Rust heartbeat（heartbeat 只检查 /api/health）。

## 建议搜索关键词

- `Tauri 2 macOS WKWebView XMLHttpRequest localhost blocked production`
- `Tauri 2 sidecar HTTP request not working bundle mode macOS`
- `WKWebView cannot fetch http://127.0.0.1 from custom protocol`
- `Tauri 2 axios not working production build macOS sidecar`

## 可能的解决方向（待验证）

1. **通过 Tauri IPC 代理所有 API 请求** — 在 Rust 端创建 invoke 命令转发 HTTP 请求到 sidecar，前端不直接发 HTTP
2. **使用 `@tauri-apps/plugin-http` 替换 axios** — 该插件通过 Rust reqwest 发请求，绕过 WebView 网络限制（但只支持 fetch，不支持 XMLHttpRequest）
3. **macOS App Transport Security (ATS) 配置** — 可能需要在 Info.plist 中添加 NSAppTransportSecurity 例外
4. **检查 macOS sandbox entitlements** — 打包后的 app 可能缺少网络访问权限

## 参考项目（声称可工作）

- [vue-tauri-fastapi-sidecar-template](https://github.com/AlanSynn/vue-tauri-fastapi-sidecar-template) — `csp: null`，标准 fetch
- [example-tauri-v2-python-server-sidecar](https://github.com/dieharders/example-tauri-v2-python-server-sidecar) — 同上
- [tauri-fastapi-full-stack-template](https://github.com/fudanglp/tauri-fastapi-full-stack-template) — axios + ureq health check
