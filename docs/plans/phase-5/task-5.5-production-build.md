# Task 5.5: 生产打包（PyInstaller + Tauri bundler）

## 输入条件

- Task 5.4 完成：端到端联调通过
- 所有工程门禁通过
- Tauri sidecar 集成可用（Task 5.1）
- 以下工具已安装：
  - Python 3.11+、pip / uv
  - PyInstaller（`pip install pyinstaller`）
  - Node.js 20+、pnpm 9+
  - Rust 1.77+（Tauri 编译需要）

## 输出物

- 创建: `frontend/src-tauri/binaries/backend-<target-triple>`（PyInstaller 产物）
- 创建: `frontend/src-tauri/target/release/bundle/`（Tauri 打包产物）
- 创建: `scripts/build.sh`（一键打包脚本）

**平台范围说明：** 本 Task 提供 `scripts/build.sh` 覆盖 macOS 和 Linux 打包。Windows 打包命令在上文中已列出（PowerShell），但不提供独立 `scripts/build.ps1` 脚本。各平台在对应原生环境上编译，不做交叉编译。

## 禁止修改

- 不修改 `backend/` 源代码（仅打包，不改功能）
- 不修改 `frontend/src/` 源代码
- 不修改 `docs/design/` 目录
- 不修改测试文件

## 实现规格

### 第一步：PyInstaller 打包 Python 后端

将 Python 后端打包为独立可执行文件（sidecar），按目标平台命名。

#### macOS (Apple Silicon)

```bash
cd backend
pip install pyinstaller
pyinstaller --onefile --name backend-aarch64-apple-darwin main.py

# 产物位置：backend/dist/backend-aarch64-apple-darwin
# 复制到 Tauri binaries 目录
cp dist/backend-aarch64-apple-darwin ../frontend/src-tauri/binaries/
```

#### macOS (Intel)

```bash
cd backend
pyinstaller --onefile --name backend-x86_64-apple-darwin main.py
cp dist/backend-x86_64-apple-darwin ../frontend/src-tauri/binaries/
```

#### Windows (x86_64)

```bash
cd backend
pyinstaller --onefile --name backend-x86_64-pc-windows-msvc main.py
# 产物：backend/dist/backend-x86_64-pc-windows-msvc.exe
copy dist\backend-x86_64-pc-windows-msvc.exe ..\frontend\src-tauri\binaries\
```

#### Linux (x86_64)

```bash
cd backend
pyinstaller --onefile --name backend-x86_64-unknown-linux-gnu main.py
cp dist/backend-x86_64-unknown-linux-gnu ../frontend/src-tauri/binaries/
```

#### PyInstaller 注意事项

- `--onefile` 打包为单个可执行文件
- 文件名必须与 `tauri.conf.json` 中 `externalBin` 的 `binaries/backend` 对应（Tauri 会自动追加平台三元组后缀）
- 打包前确认 `requirements.txt` 中所有依赖已安装
- 若有隐式导入的模块，需通过 `--hidden-import` 指定
- 打包产物体积预估：150-250 MB（含 pandas、pdfplumber 等）

#### 常见隐式导入

```bash
# 如果打包后运行报 ModuleNotFoundError，添加隐式导入：
pyinstaller --onefile \
  --name backend-aarch64-apple-darwin \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  main.py
```

### 第二步：验证 sidecar 可执行文件

```bash
# 直接运行打包产物，确认可启动
./frontend/src-tauri/binaries/backend-aarch64-apple-darwin \
  --host 127.0.0.1 --port 17396 --token test-token &
sleep 3

# 验证 health API
curl -sf -H "Authorization: Bearer test-token" \
  http://127.0.0.1:17396/api/health
# 预期返回 {"status": "ok"}

kill %1
```

### 第三步：Tauri 完整打包

```bash
cd frontend
pnpm tauri build
```

#### 产物位置

| 平台 | 产物路径 | 格式 |
|------|----------|------|
| macOS | `frontend/src-tauri/target/release/bundle/dmg/*.dmg` | DMG 镜像 |
| Windows | `frontend/src-tauri/target/release/bundle/msi/*.msi` | MSI 安装包 |
| Linux | `frontend/src-tauri/target/release/bundle/appimage/*.AppImage` | AppImage |

#### Tauri 打包注意事项

- 确认 `tauri.conf.json` 中 `bundle.externalBin` 配置正确
- 确认 `binaries/` 目录下有当前平台对应的 sidecar 可执行文件
- macOS 打包需要 Xcode Command Line Tools
- Windows 打包需要 Visual Studio Build Tools
- Linux 打包需要 `libwebkit2gtk-4.1-dev` 等依赖

### 第四步：一键打包脚本

```bash
# scripts/build.sh
#!/bin/bash
set -e

PLATFORM=$(uname -s)
ARCH=$(uname -m)

echo "=== 三方比价扫描工具 生产打包 ==="
echo "平台: $PLATFORM / $ARCH"

# 确定 target triple
case "$PLATFORM-$ARCH" in
  Darwin-arm64)  TARGET="aarch64-apple-darwin" ;;
  Darwin-x86_64) TARGET="x86_64-apple-darwin" ;;
  Linux-x86_64)  TARGET="x86_64-unknown-linux-gnu" ;;
  *)             echo "不支持的平台: $PLATFORM-$ARCH"; exit 1 ;;
esac

echo ""
echo "=== Step 1: 后端门禁检查 ==="
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest -x -q

echo ""
echo "=== Step 2: 前端门禁检查 ==="
cd ../frontend
pnpm lint
pnpm tsc --noEmit

echo ""
echo "=== Step 3: PyInstaller 打包后端 ==="
cd ../backend
pyinstaller --onefile --name "backend-$TARGET" main.py
cp "dist/backend-$TARGET" ../frontend/src-tauri/binaries/

echo ""
echo "=== Step 4: 验证 sidecar 可执行文件 ==="
"../frontend/src-tauri/binaries/backend-$TARGET" \
  --host 127.0.0.1 --port 17396 --token build-test &
SIDECAR_PID=$!
sleep 3

HEALTH=$(curl -sf -H "Authorization: Bearer build-test" \
  http://127.0.0.1:17396/api/health 2>/dev/null || echo "FAIL")
kill $SIDECAR_PID 2>/dev/null || true

if echo "$HEALTH" | grep -q '"ok"'; then
  echo "sidecar 验证通过"
else
  echo "sidecar 验证失败: $HEALTH"
  exit 1
fi

echo ""
echo "=== Step 5: Tauri 打包 ==="
cd ../frontend
pnpm tauri build

echo ""
echo "=== 打包完成 ==="
echo "产物位置: frontend/src-tauri/target/release/bundle/"
ls -la src-tauri/target/release/bundle/*/
```

Windows 用户使用对应的 `scripts/build.ps1`（PowerShell 版本，逻辑相同，target triple 为 `x86_64-pc-windows-msvc`）。

### 安装包体积预估

| 组件 | 预估体积 |
|------|----------|
| Python sidecar（PyInstaller） | 150-250 MB |
| Tauri 壳 + React 前端 | 10-30 MB |
| 总安装包 | 200-300 MB |

## 测试与验收

### 打包验证

```bash
# 1. PyInstaller 产物可独立运行
./frontend/src-tauri/binaries/backend-<target> --host 127.0.0.1 --port 17396 --token test &
sleep 3
curl -sf -H "Authorization: Bearer test" http://127.0.0.1:17396/api/health
# 预期 {"status": "ok"}
kill %1

# 2. Tauri 打包成功
ls frontend/src-tauri/target/release/bundle/
# 预期：存在 dmg/ 或 msi/ 或 appimage/ 目录

# 3. 安装包体积合理
du -sh frontend/src-tauri/target/release/bundle/dmg/*.dmg   # macOS
# 预期 < 300 MB
```

### 断言清单

- [ ] PyInstaller 打包成功（exit 0）
- [ ] sidecar 可执行文件可独立启动并响应 health API
- [ ] sidecar 可执行文件命名符合 Tauri target triple 规范
- [ ] Tauri 打包成功（exit 0）
- [ ] 安装包存在且体积在 200-300 MB 范围
- [ ] 一键打包脚本可正常执行

## 提交

```bash
# 注意：不提交打包产物（二进制文件太大）
# 仅提交打包脚本和 .gitignore 更新
git add scripts/build.sh
git commit -m "Phase 5.5: 生产打包脚本（PyInstaller + Tauri bundler）"
```

> **说明**：`frontend/src-tauri/binaries/` 目录下的 sidecar 二进制文件和 `frontend/src-tauri/target/` 目录的打包产物不提交到 Git。确认 `.gitignore` 已包含相关排除规则。
