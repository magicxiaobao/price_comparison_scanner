# Task 0.6: 前端项目骨架 + 工程门禁 + 目录规范

## 输入条件

- 仓库根目录存在，无 `frontend/` 目录
- Node.js 20+、pnpm 9+ 已安装
- Rust 1.77+（Tauri 编译需要）

## 输出物

- 创建: `frontend/` 完整目录（通过 Tauri 脚手架 + 手动调整）
- 目录结构严格符合 phase-spec.md 中的前端目录规范
- 创建: `frontend/package.json`（含所有依赖）
- 创建: `frontend/pnpm-lock.yaml`（锁定版本，必须提交）
- 创建: `frontend/tsconfig.json`（strict: true）
- 创建: `frontend/eslint.config.js`
- 创建: `frontend/vite.config.ts`（含 API proxy 配置）
- 创建: `frontend/tailwind.config.ts`
- 创建: `frontend/src/main.tsx`
- 创建: `frontend/src/App.tsx`（路由配置）
- 创建: `frontend/src/styles/globals.css`
- 创建: `frontend/src/app/home-page.tsx`（空壳 + 占位文本）
- 创建: `frontend/src/app/project-workbench.tsx`（空壳）
- 创建: `frontend/src/app/rule-management.tsx`（空壳）
- 创建: `frontend/src/components/stages/.gitkeep`
- 创建: `frontend/src-tauri/tauri.conf.json`
- 创建: `frontend/src-tauri/src/main.rs`（默认 Tauri 入口）

## 禁止修改

- 不修改 `backend/` 目录下任何文件
- 不修改 `docs/` 目录下任何文件

## 实现规格

### 步骤 1：使用 Tauri 脚手架创建项目

```bash
cd /path/to/price_comparison_scanner
pnpm create tauri-app frontend --template react-ts --manager pnpm
```

> **重要：** 脚手架输出**不是**最终目录规范。脚手架完成后，必须按 `phase-spec.md` 中定义的前端目录结构进行调整。最终目录以 phase-spec 为准，不以脚手架默认输出为准。

### 步骤 2：安装额外依赖

```bash
cd frontend
pnpm add react-router-dom @tanstack/react-table @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities zustand axios
pnpm add -D tailwindcss @tailwindcss/vite @eslint/js typescript-eslint eslint
```

### 步骤 3：配置 vite.config.ts

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:17396",
        changeOrigin: false,
      },
    },
  },
  // Tauri 开发模式下需要
  clearScreen: false,
  envPrefix: ["VITE_", "TAURI_"],
});
```

**设计要点：**
- Vite proxy 将 `/api` 转发到后端，开发模式下无需 CORS
- `envPrefix` 包含 `TAURI_` 供 Tauri 注入环境变量

### 步骤 4：配置 TypeScript

`tsconfig.json` 关键配置：
```json
{
  "compilerOptions": {
    "strict": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "moduleResolution": "bundler",
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

### 步骤 5：配置 ESLint

```javascript
// eslint.config.js
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  {
    ignores: ["dist/", "src-tauri/"],
  }
);
```

### 步骤 6：配置 Tailwind CSS

```css
/* src/styles/globals.css */
@import "tailwindcss";
```

### 步骤 7：创建路由结构

使用 `HashRouter`（非 `BrowserRouter`），原因见 phase-spec 路由模式约束。

```typescript
// src/App.tsx
import { HashRouter, Routes, Route } from "react-router-dom";
import HomePage from "./app/home-page";
import ProjectWorkbench from "./app/project-workbench";
import RuleManagement from "./app/rule-management";

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/project/:id" element={<ProjectWorkbench />} />
        <Route path="/rules" element={<RuleManagement />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
```

### 步骤 8：创建页面空壳

```typescript
// src/app/home-page.tsx
function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-2xl font-bold mb-6">三方比价支出依据扫描工具</h1>
      <div className="flex gap-4 mb-8">
        <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          + 新建项目
        </button>
        <a href="/rules" className="px-4 py-2 border rounded hover:bg-gray-100">
          规则管理
        </a>
      </div>
      <h2 className="text-lg font-semibold mb-4">最近项目</h2>
      <p className="text-gray-500">暂无项目</p>
    </div>
  );
}

export default HomePage;
```

```typescript
// src/app/project-workbench.tsx
import { useParams } from "react-router-dom";

function ProjectWorkbench() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-xl font-bold">项目工作台</h1>
      <p className="text-gray-500">项目 ID: {id}</p>
      <p className="text-gray-400">（Phase 1+ 填充）</p>
    </div>
  );
}

export default ProjectWorkbench;
```

```typescript
// src/app/rule-management.tsx
function RuleManagement() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-xl font-bold">规则管理</h1>
      <p className="text-gray-400">（Phase 2 填充）</p>
    </div>
  );
}

export default RuleManagement;
```

### 步骤 9：配置 package.json scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint src/",
    "tsc": "tsc --noEmit",
    "preview": "vite preview",
    "tauri": "tauri"
  }
}
```

### 步骤 10：配置 Tauri

`src-tauri/tauri.conf.json` 关键配置：
- `bundle.externalBin`: `["binaries/backend"]`
- `app.security.csp`: 允许 localhost:17396-17406 连接
- `app.windows[0].title`: "三方比价支出依据扫描工具"

## 测试与验收

```bash
cd frontend

# 1. 依赖已安装
test -f pnpm-lock.yaml

# 2. 工程门禁通过
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0

# 3. 开发服务器可启动
pnpm dev &
sleep 5
# 访问 http://localhost:5173 应看到首页
curl -sf http://localhost:5173 | grep -q "三方比价" && echo "✓ 首页可访问" || echo "✗ 首页不可访问"
kill %1

# 4. 目录结构检查
test -d src/app
test -d src/components
test -d src/components/stages
test -d src/lib
test -d src/stores
test -d src/types
test -d src/styles
test -f src/App.tsx
test -f src/app/home-page.tsx
test -f src/app/project-workbench.tsx
test -f src/app/rule-management.tsx
echo "✓ 目录结构正确"

# 5. TypeScript strict 模式
grep -q '"strict": true' tsconfig.json && echo "✓ strict 模式" || echo "✗ strict 模式未开启"
```

**断言清单：**
- `pnpm lint` → 退出码 0
- `pnpm tsc --noEmit` → 退出码 0
- `pnpm dev` → 开发服务器可启动
- 首页可访问，显示"三方比价支出依据扫描工具"标题
- 路由 `/project/:id` 和 `/rules` 可访问（显示占位页面）
- 目录结构与 phase-spec 前端目录规范完全一致
- `pnpm-lock.yaml` 存在
- TypeScript strict 模式已开启

## 提交

```bash
git add frontend/
git commit -m "Phase 0.6: 前端项目骨架 — React + Vite + Tailwind + Tauri + 工程门禁"
```
