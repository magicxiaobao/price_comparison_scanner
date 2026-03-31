# 白皮书交付说明

> 面向交付人员。描述白皮书产物的位置、生成方式和已知限制，无需额外口头说明即可完成接交。

---

## 一、交付产物位置

| 产物 | 路径 |
|------|------|
| 白皮书 Markdown 源文件 | `docs/whitepaper/software-whitepaper.md` |
| 截图资源目录 | `docs/whitepaper/assets/screenshots/`（10 张 `.png`） |
| 截图采集规范 | `docs/whitepaper/assets/screenshots/README.md` |
| 导出脚本 | `scripts/export_whitepaper_docx.py` |
| Word 交付件 | `dist/whitepaper/software-whitepaper.docx` |

---

## 二、重新生成 Word 文件

确保已安装依赖：

```bash
pip install python-docx
```

在项目根目录执行：

```bash
python3 scripts/export_whitepaper_docx.py
```

输出路径：`dist/whitepaper/software-whitepaper.docx`（约 1.8 MB，含 10 张嵌入截图）。

---

## 三、git 提交注意事项

`dist/` 目录已被 `.gitignore` 排除。提交 Word 文件时需使用 `--force`：

```bash
git add -f dist/whitepaper/software-whitepaper.docx
git commit -m "docs: 更新白皮书 docx 交付件"
```

Markdown 源文件和截图在 `docs/` 下，正常 `git add` 即可。

---

## 四、已知限制与注意事项

**截图来源**

全部 10 张截图均为真实界面 live-capture（Playwright 采集，视口 1600×1000，deviceScaleFactor=2）。截图对应的演示项目 UUID 见 `scripts/capture_whitepaper_screenshots.py` 中的 `PROJECT_ID` 变量。

**06 号截图（符合性审查）**

`06-compliance-stage.png` 采集自未录入需求标准时的空状态界面（显示"尚未设置需求标准"引导页），而非已填充矩阵的完整功能状态。§5.4 正文描述的是功能能力，图注已同步调整为描述空状态。若需展示已填充符合性矩阵的界面，需重新采集该截图。

**10 号截图（导出结果）**

`10-export-result.png` 为比价导出阶段 Web 界面截图（含导出文件链接），不是打开后的 Excel 文件内容视图。图注已如实说明。

**OCR 能力**

OCR 扫描件解析为实验性可选模块，需独立安装扩展（PaddleOCR），不作为 MVP 正式交付能力。白皮书 §4、§11 及文末免责说明均已注明实验性状态。

**导出脚本 Markdown 支持范围**

`scripts/export_whitepaper_docx.py` 仅支持当前白皮书实际使用的 Markdown 子集：H1/H2/H3 标题、普通段落、`**加粗**`/`*斜体*` 行内格式、本地图片、Markdown 表格、无序列表、`---` 分隔线。若白皮书后续新增代码块、嵌套列表、有序列表等结构，需同步更新脚本。

---

## 五、截图重新采集

如需重新采集截图，参见 `docs/whitepaper/assets/screenshots/README.md`，按其中的前置环境准备和截图清单执行，或直接运行：

```bash
python3 scripts/capture_whitepaper_screenshots.py
```

运行前须同时启动后端（`uvicorn main:app --host 127.0.0.1 --port 17396`）和前端（`pnpm dev`），并更新脚本中的 `PROJECT_ID` 为有完整数据的演示项目。
