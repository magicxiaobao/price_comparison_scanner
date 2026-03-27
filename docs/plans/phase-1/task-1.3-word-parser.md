# Task 1.3: DocumentParser — Word 解析器

## 输入条件

- Phase 0 全部完成
- **Task 1.2 完成**：`backend/engines/document_parser.py` 已存在（含 `parse()` 分发骨架 + `_parse_xlsx` 实现 + `_parse_docx` 占位）

## 输出物

- 修改: `backend/engines/document_parser.py`（填充 `_parse_docx` 实现）
- 修改: `backend/tests/test_document_parser.py`（新增 Word 相关测试）

## 禁止修改

- 不修改 `_parse_xlsx` 的已有实现
- 不修改 `backend/db/`
- 不修改 `backend/api/`
- 不修改 `backend/services/`
- 不修改 `frontend/`

## 实现规格

> **MCP 强制规则：** 首次使用 python-docx API 时，**必须**先通过 Context7 查文档确认 `Document()`、`document.tables`、`table.rows`、`row.cells`、`cell.text` 等用法。

### _parse_docx 实现

```python
def _parse_docx(self, file_path: str, progress_callback=None) -> list[RawTableData]:
    """
    使用 python-docx 提取 Word 文档中的所有表格。
    每个 table 生成一个 RawTableData。
    跳过完全空白的表格。
    """
    from docx import Document

    doc = Document(file_path)
    results: list[RawTableData] = []
    total_tables = len(doc.tables)

    for idx, table in enumerate(doc.tables):
        all_rows: list[list[str | None]] = []
        for row in table.rows:
            cell_values = [
                cell.text.strip() if cell.text.strip() else None
                for cell in row.cells
            ]
            all_rows.append(cell_values)

        # 跳过完全空白的表格
        has_data = any(
            any(v is not None for v in row)
            for row in all_rows
        )
        if not has_data:
            if progress_callback:
                progress_callback((idx + 1) / max(total_tables, 1))
            continue

        # 第一行作为表头
        headers = [v or "" for v in all_rows[0]] if all_rows else []
        data_rows = all_rows[1:] if len(all_rows) > 1 else []

        table_data = RawTableData(
            table_index=len(results),
            headers=headers,
            rows=data_rows,
            sheet_name=None,
            page_number=None,
            row_count=len(data_rows),
            column_count=len(headers),
        )
        results.append(table_data)

        if progress_callback:
            progress_callback((idx + 1) / max(total_tables, 1))

    return results
```

**设计要点：**
- `python-docx` 的 `Document.tables` 返回文档中所有表格
- 每个表格的每行通过 `row.cells` 访问单元格文本
- 空白单元格转为 None
- 跳过完全空白的表格
- Word 表格无 sheet_name 和 page_number，均为 None

**注意事项：**
- python-docx 对合并单元格的处理：合并单元格会在 `row.cells` 中出现重复引用，`cell.text` 会返回合并后的完整文本。MVP 阶段不特殊处理合并单元格，保留原始行为。

## 测试与验收

### 新增测试（追加到 tests/test_document_parser.py）

```python
@pytest.fixture
def sample_docx(tmp_path) -> Path:
    """生成一个包含两个表格的测试 Word 文档"""
    from docx import Document
    doc = Document()
    doc.add_paragraph("供应商报价单")

    # 表格 1
    table1 = doc.add_table(rows=3, cols=3)
    table1.cell(0, 0).text = "商品名称"
    table1.cell(0, 1).text = "单价"
    table1.cell(0, 2).text = "数量"
    table1.cell(1, 0).text = "打印机"
    table1.cell(1, 1).text = "2999"
    table1.cell(1, 2).text = "10"
    table1.cell(2, 0).text = "墨盒"
    table1.cell(2, 1).text = "199"
    table1.cell(2, 2).text = "50"

    doc.add_paragraph("其他信息")

    # 表格 2
    table2 = doc.add_table(rows=2, cols=2)
    table2.cell(0, 0).text = "型号"
    table2.cell(0, 1).text = "备注"
    table2.cell(1, 0).text = "HP-M1"
    table2.cell(1, 1).text = "含税"

    path = tmp_path / "test.docx"
    doc.save(path)
    return path


@pytest.fixture
def empty_docx(tmp_path) -> Path:
    """生成一个无表格的 Word 文档"""
    from docx import Document
    doc = Document()
    doc.add_paragraph("没有表格的文档")
    path = tmp_path / "empty.docx"
    doc.save(path)
    return path


@pytest.fixture
def blank_table_docx(tmp_path) -> Path:
    """生成一个只有空白表格的 Word 文档"""
    from docx import Document
    doc = Document()
    doc.add_table(rows=3, cols=3)  # 全空
    path = tmp_path / "blank_table.docx"
    doc.save(path)
    return path


def test_parse_docx_basic(parser, sample_docx):
    """解析含表格的 Word → 返回 2 个表格"""
    results = parser.parse(str(sample_docx))
    assert len(results) == 2

    t1 = results[0]
    assert t1.headers == ["商品名称", "单价", "数量"]
    assert t1.row_count == 2
    assert t1.column_count == 3
    assert t1.rows[0] == ["打印机", "2999", "10"]
    assert t1.sheet_name is None

    t2 = results[1]
    assert t2.headers == ["型号", "备注"]
    assert t2.row_count == 1


def test_parse_docx_no_tables(parser, empty_docx):
    """无表格的 Word → 返回空列表"""
    results = parser.parse(str(empty_docx))
    assert results == []


def test_parse_docx_blank_table(parser, blank_table_docx):
    """只有空白表格 → 跳过，返回空列表"""
    results = parser.parse(str(blank_table_docx))
    assert results == []


def test_parse_docx_progress(parser, sample_docx):
    """进度回调被正确调用"""
    progress_values = []
    parser.parse(str(sample_docx), progress_callback=lambda p: progress_values.append(p))
    assert len(progress_values) > 0
    assert progress_values[-1] <= 1.0
```

### 门禁检查

```bash
cd backend
ruff check engines/document_parser.py tests/test_document_parser.py
mypy engines/document_parser.py --ignore-missing-imports
pytest tests/test_document_parser.py -x -q
```

**断言清单：**
- 含 2 个表格的 Word → 返回 2 个 RawTableData
- 表头、数据行、row_count、column_count 均正确
- sheet_name 为 None
- 无表格的 Word → 返回空列表
- 全空白表格 → 跳过，返回空列表
- 进度回调正确调用

## 提交

```bash
git add backend/engines/document_parser.py backend/tests/test_document_parser.py
git commit -m "Phase 1.3: DocumentParser Word 解析器 — python-docx 表格提取"
```
