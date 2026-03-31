# 白皮书截图执行规范

本文档是面向执行者的截图任务说明。执行者可按本文档独立完成全部 10 张截图的采集，无需额外口头说明。

---

## 一、目录用途

本目录存放"三方比价支出依据扫描工具"产品宣传白皮书所使用的全部界面截图。截图通过 **Web + Playwright** 方式采集，目标为纯应用内容区域，不包含浏览器窗口外框、地址栏或系统桌面。

---

## 二、前置环境准备

采集前必须同时启动后端和前端开发服务器。

### 2.1 启动后端

```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 17396 --reload
```

预期状态：`http://127.0.0.1:17396/docs` 可访问，Swagger UI 正常加载。

### 2.2 启动前端

```bash
cd frontend
pnpm dev
```

预期状态：Vite 开发服务器启动，默认地址为 `http://localhost:5173`。

> **注意**：前端使用 HashRouter，所有页面 URL 形如 `http://localhost:5173/#/<path>`。
>
> 截图通过 **Playwright 浏览器访问 Vite Web 页面**进行，不通过 Tauri 桌面窗口。

### 2.3 准备演示项目

采集工作台截图（03~07）需要一个已加载数据的演示项目。建议使用 `backend/sample_projects/` 中的样例数据，或创建专用演示项目并保证以下条件：

- 已导入至少 2~3 家供应商的报价文件
- 标准化阶段已完成（存在标准化数据）
- 归组阶段已完成（存在分组结果）
- 符合性审查阶段已完成（存在符合性矩阵）
- 比价阶段已完成（存在比价结果）

记录该演示项目的 UUID，在采集 03~07 时替换 URL 中的 `:project-id`。

---

## 三、截图采集标准（Web + Playwright）

所有截图必须严格满足以下标准：

| 参数 | 值 |
|------|----|
| 视口宽度 | `1600px` |
| 视口高度 | `1000px` |
| `deviceScaleFactor` | `2`（输出为 @2x 高清图） |
| 截图内容 | **纯应用内容区域** |
| 浏览器外框 | **不得出现**（地址栏、标签页、工具栏均不可见） |
| 系统桌面 | **不得出现** |
| Tauri 窗口边框 | **不得出现**（Playwright 访问 Web，不通过 Tauri） |
| 文件格式 | `.png` |
| 图片命名 | 严格按截图清单中的文件名 |

### 推荐 Playwright 截图方式

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        device_scale_factor=2,
    )
    page = context.new_page()
    page.goto("http://localhost:5173/#/")
    # 等待页面稳定后截图
    page.wait_for_load_state("networkidle")
    page.screenshot(path="docs/whitepaper/assets/screenshots/01-home.png")
    browser.close()
```

截图输出路径统一为 `docs/whitepaper/assets/screenshots/<文件名>.png`（相对于项目根目录）。

---

## 四、截图清单

### 完整清单表

| 编号 | 文件名 | 画面内容 | 目标 URL | 前置状态要求 | 用途章节 | 预期采集方式 | 实际来源类型（采集后回填） | 设计图 fallback |
|------|--------|----------|----------|--------------|----------|--------------|----------------------------|-----------------|
| 01 | `01-home.png` | 首页 / 最近项目列表 | `http://localhost:5173/#/` | 至少存在 1 个已有项目（显示在最近项目列表） | §1 产品概述、§9 典型界面展示 | live-capture | - | `docs/design/ui/home/screen.png` |
| 02 | `02-create-project-dialog.png` | 新建项目弹窗（打开状态） | `http://localhost:5173/#/` | 首页已打开，点击"新建项目"触发弹窗 | §9 典型界面展示 | live-capture | - | `docs/design/ui/dialogs/screen.png` |
| 03 | `03-import-stage.png` | 文件导入阶段 | `http://localhost:5173/#/project/:project-id` | 工作台已加载，点击"导入文件"标签，已显示已上传文件列表 | §5.1 文件导入 | live-capture | - | `docs/design/ui/import-stage/screen.png` |
| 04 | `04-standardize-stage.png` | 标准化阶段表格 | `http://localhost:5173/#/project/:project-id` | 工作台已加载，点击"标准化"标签，标准化表格已显示数据行 | §5.2 字段标准化 | live-capture | - | `docs/design/ui/standardize-stage/screen.png` |
| 05 | `05-grouping-stage.png` | 商品归组界面 | `http://localhost:5173/#/project/:project-id` | 工作台已加载，点击"商品归组"标签，商品分组卡片已显示 | §5.3 商品归组 | live-capture | - | `docs/design/ui/grouping-stage/screen.png` |
| 06 | `06-compliance-stage.png` | 符合性审查界面（矩阵已加载） | `http://localhost:5173/#/project/:project-id` | 工作台已加载，点击"符合性审查"标签，符合性矩阵已显示 | §5.4 符合性审查 | live-capture | - | `docs/design/ui/compliance-matrix/screen.png` |
| 07 | `07-comparison-stage.png` | 比价结果界面（表格已加载） | `http://localhost:5173/#/project/:project-id` | 工作台已加载，点击"比价导出"标签，比价结果表格已显示 | §5.5 比价结果与导出 | live-capture | - | `docs/design/ui/comparison-export/screen.png` |
| 08 | `08-rule-management.png` | 规则管理页面 | `http://localhost:5173/#/rules` | 直接访问，规则列表已显示（可为空列表） | §6 关键产品亮点 | live-capture | - | `docs/design/ui/rule-management/screen.png` |
| 09 | `09-app-preferences.png` | 应用设置页面 | `http://localhost:5173/#/preferences` | 直接访问，设置项已显示 | §8 数据安全与部署优势 | live-capture | - | `docs/design/ui/app-preferences/screen.png` |
| 10 | `10-export-result.png` | 导出后的底稿（Excel 导出成功提示或文件预览） | `http://localhost:5173/#/project/:project-id` | 工作台已加载，点击"比价导出"标签，点击导出后截取导出成功提示或打开导出文件进行截图 | §10 交付成果与验收价值 | export-capture | - | `docs/design/ui/comparison-export/screen.png` |

### 阶段导航说明

工作台（`/project/:project-id`）的阶段由 React 状态控制，**不体现在 URL 中**。执行者需通过页面顶部的阶段导航标签切换至目标阶段：

| 截图编号 | 阶段索引 | 阶段标签名（界面真实文本） |
|----------|----------|-----------------------------|
| 03 | 0 | `导入文件` |
| 04 | 1 | `标准化` |
| 05 | 2 | `商品归组` |
| 06 | 3 | `符合性审查` |
| 07、10 | 4 | `比价导出` |

Playwright 切换阶段示例：通过 `page.click()` 点击阶段导航标签，并等待 `networkidle` 后截图。

---

## 五、来源类型与 fallback 规则

### 5.1 来源类型定义

| 类型标识 | 含义 |
|----------|------|
| `live-capture` | 通过 Playwright 采集的真实运行界面截图 |
| `export-capture` | 对真实导出产物（如 Excel 文件）的截图 |
| `design-fallback` | 来自 `docs/design/ui/*/screen.png` 的设计图补位截图 |

### 5.2 fallback 触发条件

仅在以下情形下允许使用设计图 fallback：

- 真实运行界面无法在截图会话内稳定复现（如数据依赖无法满足）
- 对应阶段功能尚未实现或存在严重 UI 异常

**使用 fallback 时的强制要求**：

1. 在本文档截图清单表的"实际来源类型（采集后回填）"列填写 `design-fallback`
2. 在截图文件旁创建同名 `.meta.txt` 文件，注明 fallback 原因和设计图来源路径
3. 不得将设计图 fallback 混入 `live-capture` 类型，不得虚报来源

### 5.3 已知可用设计图文件（fallback 路径）

| 截图编号 | 设计图路径 |
|----------|------------|
| 01 | `docs/design/ui/home/screen.png` |
| 02 | `docs/design/ui/dialogs/screen.png` |
| 03 | `docs/design/ui/import-stage/screen.png` |
| 04 | `docs/design/ui/standardize-stage/screen.png` |
| 05 | `docs/design/ui/grouping-stage/screen.png` |
| 06 | `docs/design/ui/compliance-matrix/screen.png` |
| 07 | `docs/design/ui/comparison-export/screen.png` |
| 08 | `docs/design/ui/rule-management/screen.png` |
| 09 | `docs/design/ui/app-preferences/screen.png` |
| 10 | `docs/design/ui/comparison-export/screen.png` |

> `docs/design/ui/workbench-shell/screen.png` 为工作台通用 shell 截图，无直接对应编号，可作为辅助参考但不用于白皮书截图。

---

## 六、采集后更新说明

每张截图采集完成后，执行者须更新第四节截图清单表中对应行的"实际来源类型（采集后回填）"列：

- 真实界面采集成功 → 填写 `live-capture`
- 导出文件截图 → 填写 `export-capture`
- 使用设计图补位 → 填写 `design-fallback`（并按 5.2 节要求创建 `.meta.txt`）

---

## 七、命名规范

截图文件统一采用两位数字前缀 + 语义名称，扩展名 `.png`：

```
<序号>-<语义名称>.png
```

10 个固定文件名（不得修改，须与白皮书正文中的图片引用路径一致）：

```
01-home.png
02-create-project-dialog.png
03-import-stage.png
04-standardize-stage.png
05-grouping-stage.png
06-compliance-stage.png
07-comparison-stage.png
08-rule-management.png
09-app-preferences.png
10-export-result.png
```
