# Tauri macOS WKWebView HTTP 请求阻止问题 — 修复总结

> 状态：**已解决** | 日期：2026-03-29

## 问题描述

Tauri 2 macOS 桌面应用，前端（React + axios）无法通过 HTTP 请求访问本地 sidecar（FastAPI on 127.0.0.1）。开发模式正常，`pnpm tauri build` 打包 DMG 后完全不通。

**核心现象**：Tauri IPC（`invoke`）正常，但 WebView 内的 HTTP 请求（axios/XMLHttpRequest）完全不到达后端 sidecar。access.log 中零条来自 WebView 的请求。

## 根因分析

macOS 打包后的 WKWebView 阻止了对 `http://127.0.0.1` 的直接 HTTP 请求。这是 WKWebView 在 bundle 模式下的安全限制，与 CORS、CSP、ATS 均无关。

## 修复方案：`@tauri-apps/plugin-http` + 自定义 axios adapter

### 核心思路

将桌面态的 HTTP 传输层从浏览器网络栈（XMLHttpRequest）切换到 Rust 网络栈（reqwest），绕过 WKWebView 限制。通过 axios 自定义 adapter 实现，所有 API 函数零修改。

### 架构

```
所有 API 函数 → client.get/post/put/delete (axios)
                    ↓
              tauriHttpAdapter (Tauri 模式自动激活)
                    ↓
              @tauri-apps/plugin-http fetch (Rust reqwest)
                    ↓
              FastAPI sidecar (127.0.0.1:17396)
```

开发模式下 axios 使用默认 adapter（浏览器 XMLHttpRequest），不受影响。

### 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `frontend/src-tauri/Cargo.toml` | 添加 `tauri-plugin-http = { version = "2", features = ["multipart"] }`，移除 `tauri-plugin-localhost` |
| `frontend/src-tauri/src/lib.rs` | 注册 `tauri_plugin_http::init()`，移除 localhost plugin 相关代码 |
| `frontend/src-tauri/capabilities/default.json` | 添加 `http:default` 权限，放行端口 17396-17405（127.0.0.1 + localhost） |
| `frontend/src/lib/api.ts` | 添加 `tauriHttpAdapter`、`ensureTauriFetch`；修改 axios 客户端 Content-Type 设置方式 |
| `frontend/package.json` | 添加 `@tauri-apps/plugin-http` 依赖 |
| `frontend/src-tauri/tauri.conf.json` | 移除 `"useHttpsScheme": false` |
| `frontend/src/stores/project-store.ts` | 所有异步函数添加 try-catch 防止 UI 卡死 |
| `frontend/src/components/create-project-dialog.tsx` | 添加错误状态显示（红色提示框） |
| `backend/main.py` | 添加全局异常处理器，500 错误写入 error.log 并返回具体异常信息 |
| `backend/api/middleware.py` | access.log 增强：添加响应状态码 + 耗时；4xx/5xx 额外写 error.log |

### PyInstaller 打包

```bash
pyinstaller --onefile --name backend-aarch64-apple-darwin --add-data "db/schema.sql:db" main.py
```

必须用 `--add-data` 包含 `db/schema.sql`，否则 sidecar 创建项目时 500（FileNotFoundError）。

## 修复过程中发现的三个子问题

### 1. PyInstaller 未打包 schema.sql

**现象**：POST /api/projects 返回 500
**根因**：`database.py` 用 `Path(__file__).parent / "schema.sql"` 加载建表脚本，但 PyInstaller 默认不打包 `.sql` 文件
**修复**：PyInstaller 命令添加 `--add-data "db/schema.sql:db"`

### 2. Tauri plugin-http 的 JS→Rust IPC 不支持 FormData 自动序列化

**现象**：文件上传 POST 返回 422 `Field required: file`
**根因**：`@tauri-apps/plugin-http` 的 fetch 无法通过 JS→Rust IPC 桥接自动将浏览器 FormData 对象序列化为 multipart/form-data。即使启用了 Cargo `multipart` feature，FormData 内容在跨进程传输时丢失。
**修复**：在 adapter 中手动构造 multipart/form-data body — 遍历 FormData entries，File 用 `arrayBuffer()` 读取二进制，手动拼接 boundary + Content-Disposition + body。

### 3. axios 默认 Content-Type 导致 FormData 被 JSON 序列化

**现象**：手动 multipart 代码不执行，`config.data instanceof FormData` 检查为 false
**根因**：axios 客户端设置了 `headers: { "Content-Type": "application/json" }` 作为默认值。axios 的 `transformRequest` 在 adapter 之前执行，看到 Content-Type 是 `application/json` 后，会对 FormData 调用 `JSON.stringify()`，导致 adapter 收到的 `config.data` 已经是字符串而非 FormData 对象。
**修复**：移除 axios 客户端的默认 Content-Type，改用请求拦截器按需设置 — 非 FormData 请求设 `application/json`，FormData 请求不设（由 adapter 处理）。

## 日志体系增强

### access.log（后端）

```
2026-03-29 11:36:42 GET /api/projects/xxx 200 5ms auth=yes ua=tauri-plugin-http/2.5.7 origin=tauri://localhost
```

字段：时间 | 方法 | 路径 | **状态码** | **耗时** | 认证 | UA | Origin

### error.log（后端）

- 4xx/5xx 请求自动记录：请求 Content-Type + 响应 body（截取前 200 字符）
- 未捕获异常自动记录：完整 traceback

### 前端日志

adapter 输出 `[tauri-http] → METHOD url` 和 `[tauri-http] ← status ok` 到 console。

## 已排除的方案

| 方案 | 排除原因 |
|------|----------|
| CORS 配置 | 请求根本没到达后端，不是 CORS 问题 |
| `csp: null` | CSP 不影响 WKWebView 的 HTTP 请求拦截 |
| `useHttpsScheme: false` | 不改变 WKWebView 对 localhost HTTP 的限制 |
| `tauri-plugin-localhost` | 该插件用于将前端资产从 localhost 提供，不解决 sidecar HTTP 问题 |
| ATS / Info.plist | 补充措施，不是主要修复方向 |
| Tauri IPC 代理 | 可行但需大量 Rust 代码，不如 plugin-http adapter 方案简洁 |

## 关键经验

1. **macOS WKWebView bundle 模式**下不能直接发 HTTP 请求到 localhost，必须通过 Rust 网络栈
2. **Tauri plugin-http 的 JS fetch 不支持 FormData 自动序列化**，需手动构造 multipart body
3. **axios 默认 Content-Type 会影响 transformRequest 的序列化行为**，FormData 场景下不能设 `application/json` 默认值
4. **PyInstaller 打包时必须显式包含非 Python 数据文件**（如 `.sql`、`.json`）
5. **完善的日志体系（access.log + error.log）是高效调试的前提**
