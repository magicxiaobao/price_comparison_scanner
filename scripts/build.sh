#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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
cd "$PROJECT_ROOT/backend"
ruff check .
mypy . --ignore-missing-imports
pytest -x -q

echo ""
echo "=== Step 2: 前端门禁检查 ==="
cd "$PROJECT_ROOT/frontend"
pnpm lint
pnpm exec tsc --noEmit

echo ""
echo "=== Step 3: PyInstaller --onedir 打包后端 ==="
cd "$PROJECT_ROOT/backend"
pyinstaller --onedir --clean --noconfirm \
  --name backend \
  --collect-submodules uvicorn \
  --paths "$PROJECT_ROOT/backend/" \
  --add-data "db/schema.sql:db" \
  --distpath ./dist \
  main.py

# 复制 onedir 产物到 Tauri resources
SIDECAR_DEST="$PROJECT_ROOT/frontend/src-tauri/resources/sidecar"
rm -rf "$SIDECAR_DEST"
cp -r "dist/backend" "$SIDECAR_DEST"
chmod -R u+x "$SIDECAR_DEST"

echo ""
echo "=== Step 4: 验证 sidecar 可执行文件 ==="
"$SIDECAR_DEST/backend" \
  --host 127.0.0.1 --port 17396 --token build-test &
SIDECAR_PID=$!
sleep 3

HEALTH=$(curl -sf -H "Authorization: Bearer build-test" \
  http://127.0.0.1:17396/api/health 2>/dev/null || echo "FAIL")
kill $SIDECAR_PID 2>/dev/null || true
wait $SIDECAR_PID 2>/dev/null || true

if echo "$HEALTH" | grep -q '"ok"'; then
  echo "sidecar 验证通过"
else
  echo "sidecar 验证失败: $HEALTH"
  exit 1
fi

echo ""
echo "=== Step 5: Tauri 打包（跳过 sidecar 自动签名检查） ==="
cd "$PROJECT_ROOT/frontend"
TAURI_SKIP_SIDECAR_SIGNATURE_CHECK=true pnpm tauri build

echo ""
echo "=== Step 6: Ad-hoc 签名（macOS） ==="
APP_PATH="src-tauri/target/release/bundle/macos/price-comparison-scanner.app"
if [ -d "$APP_PATH" ]; then
    codesign --force --deep -s - "$APP_PATH"
    echo "Ad-hoc 签名完成: $APP_PATH"
else
    echo "跳过签名（未找到 .app 产物）"
fi

echo ""
echo "=== 打包完成 ==="
echo "产物位置: frontend/src-tauri/target/release/bundle/"
ls -lh src-tauri/target/release/bundle/dmg/*.dmg 2>/dev/null || true
ls -lh src-tauri/target/release/bundle/macos/*.app 2>/dev/null || true
ls -lh src-tauri/target/release/bundle/appimage/*.AppImage 2>/dev/null || true
