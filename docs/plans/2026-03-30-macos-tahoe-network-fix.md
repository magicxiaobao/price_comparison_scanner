# macOS Tahoe 网络兼容性修复 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 macOS Tahoe 26.x 升级后 Tauri 应用无法连接本地 sidecar 的问题，统一使用原生 fetch + TCP 检测方案。

**Architecture:** macOS Tahoe 收紧了对 ad-hoc 签名应用的网络限制，导致 Rust 侧 reqwest（被 `@tauri-apps/plugin-http` 和 `lib.rs` health check 使用）无法发出 HTTP 请求。方案：前端 API 改用浏览器原生 fetch，Rust 侧启动检测 / 心跳改用 TCP 端口连接，macOS 通过 Info.plist 的 `NSAllowsLocalNetworking` 放行 localhost HTTP。

**Tech Stack:** Tauri 2.x, WKWebView (macOS), WebView2 (Windows), Info.plist ATS 配置

**参考资料:**
- [Apple - NSAllowsLocalNetworking](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking)
- [tauri-apps/tauri#13878 - macOS Production Build Network Blocked](https://github.com/tauri-apps/tauri/issues/13878)
- [home-assistant/iOS#4192 - macOS Tahoe Local Network Permission](https://github.com/home-assistant/iOS/issues/4192)
- [Tauri - macOS Application Bundle](https://v2.tauri.app/distribute/macos-application-bundle/)

---

## 背景

- **commitId `0712706`** 是最后一个功能正常的版本（macOS 升级前打包）
- macOS 升级到 Tahoe 26.x 后，即使用 `0712706` 的代码重新打包也出现相同问题
- 问题 1: `lib.rs` 中 reqwest health check 超时 → sidecar 启动失败
- 问题 2: `@tauri-apps/plugin-http`（内部也用 reqwest）返回 502 → API 请求全部失败
- 根因: macOS Tahoe 阻止 ad-hoc 签名应用的 Rust reqwest 发出 HTTP 请求

## 变更范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src-tauri/Info.plist` | 新建 | ATS 配置，允许 localhost HTTP |
| `frontend/src-tauri/src/lib.rs` | 修改 | health check / heartbeat 改 TCP，cleanup 改直接 kill，添加 xattr 清除 |
| `frontend/src/lib/api.ts` | 修改 | 移除 plugin-http 依赖，改用原生 fetch |
| `frontend/src-tauri/Cargo.toml` | 不改 | 保留 reqwest（tauri-plugin-http 仍在依赖树中，不影响） |

## 不变范围

- `backend/` 目录所有文件不修改
- `frontend/src-tauri/tauri.conf.json` 不修改
- `frontend/src-tauri/Cargo.toml` 不修改
- Windows 打包行为不受影响（`#[cfg]` 条件编译隔离 macOS 特有逻辑）

---

### Task 1: 新建 Info.plist — 配置 NSAllowsLocalNetworking

**Files:**
- 新建: `frontend/src-tauri/Info.plist`

**说明:** Tauri 构建时会自动将 `src-tauri/Info.plist` 合并到最终 app bundle 的 Info.plist 中。添加 `NSAllowsLocalNetworking = true` 允许 WKWebView 的原生 fetch 访问 `http://127.0.0.1`。

**Step 1: 创建 Info.plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
  </dict>
</dict>
</plist>
```

**Step 2: 验证文件格式**

```bash
plutil -lint frontend/src-tauri/Info.plist
# 预期: frontend/src-tauri/Info.plist: OK
```

**Step 3: 提交**

```bash
git add frontend/src-tauri/Info.plist
git commit -m "feat(tauri): 添加 Info.plist 配置 NSAllowsLocalNetworking 放行 localhost HTTP"
```

---

### Task 2: 修改 lib.rs — 替换 reqwest 为 TCP 检测

**Files:**
- 修改: `frontend/src-tauri/src/lib.rs`

**说明:** 将三处 reqwest 使用替换为不受 macOS 网络限制的方案：
1. **health check**: reqwest HTTP GET → `TcpStream::connect_timeout`（端口可连即视为就绪）
2. **heartbeat**: reqwest HTTP GET → `TcpStream::connect_timeout`
3. **cleanup**: reqwest POST /shutdown → 直接 `kill_pid` + `child.kill()`
4. **新增**: macOS 上启动前 `xattr -cr` 清除 sidecar 隔离标记

**变更原则:**
- 所有 macOS 特有逻辑用 `#[cfg(target_os = "macos")]` 保护
- Unix 通用逻辑用 `#[cfg(unix)]` 保护
- Windows 行为完全不变

**Step 1: 应用 lib.rs 改动**

当前工作区已有正确的 diff（TCP health check + xattr + cleanup 改动）。确认 diff 内容与计划一致。

**Step 2: 编译验证**

```bash
cd frontend && pnpm tauri build --bundles dmg 2>&1 | tail -5
# 预期: Finished 1 bundle at: ...dmg
```

**Step 3: 提交**

```bash
git add frontend/src-tauri/src/lib.rs
git commit -m "fix(tauri): health check/heartbeat 改用 TCP 替代 reqwest，兼容 macOS Tahoe"
```

---

### Task 3: 修改 api.ts — 原生 fetch 替代 plugin-http

**Files:**
- 修改: `frontend/src/lib/api.ts`

**说明:** 移除 `@tauri-apps/plugin-http` 的动态导入和 `ensureTauriFetch` 函数，直接使用 `globalThis.fetch`。`@tauri-apps/plugin-http` npm 包和 Cargo 依赖暂保留（避免不必要的依赖树变动），仅不再运行时调用。

**变更范围:** 仅修改 `tauriHttpAdapter` 函数开头的 fetch 获取方式，其余逻辑（headers 构建、FormData 处理、response 解析）完全不变。

**Step 1: 应用 api.ts 改动**

当前工作区已有正确的 diff。确认变更：
- 删除 `tauriFetchPromise` 变量和 `ensureTauriFetch` 函数
- `tauriHttpAdapter` 开头改为 `const fetchFn = globalThis.fetch.bind(globalThis)`

**Step 2: TypeScript 编译验证**

```bash
cd frontend && pnpm tsc --noEmit
# 预期: 无错误
```

**Step 3: 提交**

```bash
git add frontend/src/lib/api.ts
git commit -m "fix(frontend): API 请求改用原生 fetch 替代 plugin-http，兼容 macOS Tahoe"
```

---

### Task 4: macOS 本地打包验证

**前置:** Task 1-3 全部提交

**Step 1: 清理环境**

```bash
pkill -f "sidecar/backend" 2>/dev/null
rm -rf ~/.price-comparison-scanner/
```

**Step 2: 构建 sidecar + DMG**

```bash
cd backend && .venv/bin/pyinstaller backend.spec --noconfirm
rm -rf ../frontend/src-tauri/resources/sidecar
mkdir -p ../frontend/src-tauri/resources/sidecar
cp -R dist/backend/* ../frontend/src-tauri/resources/sidecar/
cd ../frontend && pnpm tauri build --bundles dmg
```

**Step 3: 安装并验证**

```bash
open frontend/src-tauri/target/release/bundle/dmg/price-comparison-scanner_0.1.0_aarch64.dmg
```

验收标准:
- [ ] 应用启动成功，无 sidecar 超时
- [ ] sidecar.log 显示 `health check passed`
- [ ] 首页显示两个示例项目
- [ ] 创建新项目成功（无 502）
- [ ] 进入项目工作台，导入/标准化/归组等阶段可正常操作
- [ ] 规则管理页面有默认规则

**Step 4: 验证 Info.plist 合并**

```bash
plutil -p /Applications/price-comparison-scanner.app/Contents/Info.plist | grep -A3 NSAppTransportSecurity
# 预期: 包含 NSAllowsLocalNetworking = true
```

---

### Task 5: 推送并触发 Windows 构建验证

**Step 1: 推送到 GitHub**

```bash
git push origin master
```

**Step 2: 触发 Windows 构建**

```bash
gh workflow run build-windows.yml --repo magicxiaobao/price_comparison_scanner --ref master
```

**Step 3: 监控构建**

```bash
gh run watch <run-id> --repo magicxiaobao/price_comparison_scanner
```

验收标准:
- [ ] Windows 构建成功
- [ ] 产物中有 NSIS .exe 安装包

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| `NSAllowsLocalNetworking` 在 Tahoe 26.x 不生效 | 低 | 高 | Apple 官方文档明确支持此配置 |
| Windows WebView2 原生 fetch 调 localhost 被阻止 | 极低 | 高 | WebView2 无 ATS 限制，且之前 fetch 能工作 |
| 移除 plugin-http 调用后文件上传（FormData）不工作 | 低 | 中 | adapter 中 FormData 手动构造逻辑保留，与 fetch 实现无关 |
| Info.plist 未被 Tauri 正确合并 | 低 | 中 | Task 4 Step 4 验证合并结果 |
