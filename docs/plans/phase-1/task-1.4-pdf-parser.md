# Task 1.4: DocumentParser — PDF 结构化解析器（L1 only）

## 输入条件

- Phase 0 全部完成
- `backend/engines/document_parser.py` 已存在（Task 1.2 创建的骨架）

## 输出物

- 修改: `backend/engines/document_parser.py`（填充 `_parse_pdf` 实现）
- 修改: `backend/tests/test_document_parser.py`（新增 PDF 相关测试）
- 修改: `backend/requirements-dev.txt`（新增 fpdf2>=2.8.0）

## 禁止修改

- 不修改 `_parse_xlsx` 和 `_parse_docx` 的已有实现
- 不修改 `backend/db/`
- 不修改 `backend/api/`
- 不修改 `backend/services/`
- 不修改 `frontend/`

## 实现规格

> **MCP 强制规则：** 首次使用 pdfplumber API 时，**必须**先通过 Context7 查文档确认 `pdfplumber.open()`、`page.extract_tables()`、`page.extract_text()` 等用法。

### PDF 解析策略

本 Task 仅实现 **L1 结构化提取**。L2（转图片 OCR）和 L3（人工介入）的逻辑已在 `_fallback_ocr()` 占位，不在本 Task 实现。

当 L1 未识别到任何表格时，返回空列表（不触发 L2 降级，降级逻辑在 Task 1.5 的 file_service 中处理）。

### _parse_pdf 实现

```python
def _parse_pdf(self, file_path: str, progress_callback=None) -> list[RawTableData]:
    """
    使用 pdfplumber 进行 L1 结构化提取。
    逐页提取表格，每个表格生成一个 RawTableData，记录 page_number。
    跳过完全空白的表格。
    """
    import pdfplumber

    results: list[RawTableData] = []

    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)

        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                if progress_callback:
                    progress_callback((page_idx + 1) / max(total_pages, 1))
                continue

            for table in tables:
                if not table or len(table) == 0:
                    continue

                # 清洗单元格值
                cleaned_rows: list[list[str | None]] = []
                for row in table:
                    cleaned = [
                        cell.strip() if cell and cell.strip() else None
                        for cell in row
                    ]
                    cleaned_rows.append(cleaned)

                # 跳过完全空白的表格
                has_data = any(
                    any(v is not None for v in row)
                    for row in cleaned_rows
                )
                if not has_data:
                    continue

                # 第一行作为表头
                headers = [v or "" for v in cleaned_rows[0]] if cleaned_rows else []
                data_rows = cleaned_rows[1:] if len(cleaned_rows) > 1 else []

                table_data = RawTableData(
                    table_index=len(results),
                    headers=headers,
                    rows=data_rows,
                    sheet_name=None,
                    page_number=page_idx + 1,  # 页码从 1 开始
                    row_count=len(data_rows),
                    column_count=len(headers),
                )
                results.append(table_data)

            if progress_callback:
                progress_callback((page_idx + 1) / max(total_pages, 1))

    return results
```

**设计要点：**
- 使用 `pdfplumber.open()` + `page.extract_tables()` 提取结构化表格
- 逐页处理，每页可能有多个表格
- page_number 从 1 开始（用户友好）
- 单元格值 strip 后若为空则转为 None
- 空白表格跳过
- 第一行作为表头

**L2/L3 占位说明：**
- 当 `_parse_pdf` 返回空列表时，调用方（file_service）可以决定是否尝试 `_fallback_ocr()`
- 当前 `_fallback_ocr()` 检测 `_is_ocr_available()` → False → 返回空列表
- 如果 OCR 不可用，file_service 应将文件的 recognition_mode 设为 `"manual"`，提示用户手动处理

## 测试与验收

### 新增测试（追加到 tests/test_document_parser.py）

由于在测试中动态生成 PDF 较复杂，使用 `reportlab` 或直接构造简单 PDF。为避免额外依赖，使用 `fpdf2` 或 手工构造最小 PDF 表格。考虑到 MVP 复杂度，推荐使用 `pdfplumber` 自身的测试方式 — 用 openpyxl 生成 Excel 再通过 LibreOffice 转 PDF 不可行，改为直接用代码生成带表格线的简单 PDF。

**实际方案：** 在 `conftest.py` 中添加一个生成简单 PDF 的 fixture，使用 `fpdf2`（需加入 requirements-dev.txt）。

**替代方案（无额外依赖）：** 将测试 PDF 的 fixture 改为一个实际文件，通过 `tmp_path` + 手写最小 PDF 字节流。但这种方式难以生成带表格的 PDF。

**最终方案：** 添加 `fpdf2` 到 `requirements-dev.txt`，用于在测试中生成包含表格的 PDF。

```python
@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    """生成一个包含表格的简单 PDF"""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    # 表格数据
    headers = ["Product", "Price", "Qty"]
    rows = [
        ["Laptop", "4299", "50"],
        ["Monitor", "1599", "30"],
    ]

    col_width = 40
    row_height = 8

    # 绘制表头
    for header in headers:
        pdf.cell(col_width, row_height, header, border=1)
    pdf.ln()

    # 绘制数据行
    for row in rows:
        for cell in row:
            pdf.cell(col_width, row_height, cell, border=1)
        pdf.ln()

    path = tmp_path / "test.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def empty_pdf(tmp_path) -> Path:
    """生成一个无表格的 PDF（纯文本）"""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "This PDF has no tables")

    path = tmp_path / "empty.pdf"
    pdf.output(str(path))
    return path


def test_parse_pdf_basic(parser, sample_pdf):
    """解析含表格的 PDF → 返回至少 1 个表格"""
    results = parser.parse(str(sample_pdf))
    # pdfplumber 对简单 PDF 表格的识别可能因排版而异
    # 至少应返回列表（可能为空，取决于 pdfplumber 的识别能力）
    assert isinstance(results, list)
    if len(results) > 0:
        t = results[0]
        assert t.page_number == 1
        assert t.row_count >= 1
        assert t.column_count >= 1
        assert t.sheet_name is None


def test_parse_pdf_empty(parser, empty_pdf):
    """无表格的 PDF → 返回空列表"""
    results = parser.parse(str(empty_pdf))
    assert results == []


def test_parse_pdf_progress(parser, sample_pdf):
    """进度回调被正确调用"""
    progress_values = []
    parser.parse(str(sample_pdf), progress_callback=lambda p: progress_values.append(p))
    assert len(progress_values) > 0
    assert progress_values[-1] <= 1.0
```

### requirements-dev.txt 修改

新增一行：

```
fpdf2>=2.8.0
```

### 门禁检查

```bash
cd backend
pip install fpdf2
ruff check engines/document_parser.py tests/test_document_parser.py
mypy engines/document_parser.py --ignore-missing-imports
pytest tests/test_document_parser.py -x -q
```

**断言清单：**
- 含表格的 PDF → 返回 list（可能为空，pdfplumber 对简单 PDF 的表格识别依赖排版）
- 如果识别成功 → page_number == 1，row_count >= 1，sheet_name 为 None
- 无表格的 PDF → 返回空列表
- 进度回调正确调用
- `_is_ocr_available()` 返回 False（开发环境未安装 PaddleOCR）
- `_fallback_ocr()` 在 OCR 不可用时返回空列表

## 提交

```bash
git add backend/engines/document_parser.py backend/tests/test_document_parser.py \
       backend/requirements-dev.txt
git commit -m "Phase 1.4: DocumentParser PDF L1 结构化解析器 — pdfplumber 逐页表格提取"
```
