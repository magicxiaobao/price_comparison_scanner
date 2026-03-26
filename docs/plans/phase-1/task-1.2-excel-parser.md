# Task 1.2: DocumentParser — Excel 解析器

## 输入条件

- Phase 0 全部完成
- `backend/engines/` 目录已存在

## 输出物

- 创建: `backend/engines/document_parser.py`（首次创建，本 Task 仅实现 `_parse_xlsx` 和 `parse` 的分发骨架）
- 创建: `backend/tests/test_document_parser.py`（Excel 相关测试）

## 禁止修改

- 不修改 `backend/db/`（repo 由 Task 1.5 创建）
- 不修改 `backend/api/`
- 不修改 `backend/services/`
- 不修改 `frontend/`

## 实现规格

> **MCP 强制规则：** 首次使用 openpyxl API 时，**必须**先通过 Context7 查文档确认 `load_workbook()`、`ws.iter_rows()`、`ws.max_row`、`ws.max_column` 等用法。

### engines/document_parser.py

```python
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class RawTableData:
    """解析器内部使用的原始表格数据结构"""
    table_index: int
    headers: list[str]              # 表头行
    rows: list[list[str | None]]    # 数据行（每行为单元格值列表）
    sheet_name: str | None = None   # Excel sheet 名
    page_number: int | None = None  # PDF 页码
    row_count: int = 0
    column_count: int = 0


class DocumentParser:
    """
    根据文件类型自动分发到对应解析器。
    返回 RawTableData 列表。
    """

    SUPPORTED_TYPES = {"xlsx", "docx", "pdf"}

    def parse(self, file_path: str, progress_callback=None) -> list[RawTableData]:
        """
        解析文件，返回 RawTableData 列表。
        progress_callback: 可选，用于报告进度（0.0-1.0）。
        """
        path = Path(file_path)
        suffix = path.suffix.lower().lstrip(".")

        if suffix == "xlsx":
            return self._parse_xlsx(file_path, progress_callback)
        elif suffix == "docx":
            return self._parse_docx(file_path, progress_callback)
        elif suffix == "pdf":
            return self._parse_pdf(file_path, progress_callback)
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")

    def _parse_xlsx(self, file_path: str, progress_callback=None) -> list[RawTableData]:
        """
        使用 openpyxl 读取 Excel 文件。
        每个 sheet 生成一个 RawTableData。
        跳过完全空白的 sheet。
        """
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        results: list[RawTableData] = []
        sheet_names = wb.sheetnames
        total_sheets = len(sheet_names)

        for idx, sheet_name in enumerate(sheet_names):
            ws = wb[sheet_name]

            all_rows: list[list[str | None]] = []
            for row in ws.iter_rows():
                cell_values = [
                    str(cell.value).strip() if cell.value is not None else None
                    for cell in row
                ]
                all_rows.append(cell_values)

            # 跳过完全空白的 sheet
            has_data = any(
                any(v is not None for v in row)
                for row in all_rows
            )
            if not has_data:
                if progress_callback:
                    progress_callback((idx + 1) / total_sheets)
                continue

            # 第一行作为表头
            headers = [v or "" for v in all_rows[0]] if all_rows else []
            data_rows = all_rows[1:] if len(all_rows) > 1 else []

            table = RawTableData(
                table_index=len(results),
                headers=headers,
                rows=data_rows,
                sheet_name=sheet_name,
                row_count=len(data_rows),
                column_count=len(headers),
            )
            results.append(table)

            if progress_callback:
                progress_callback((idx + 1) / total_sheets)

        wb.close()
        return results

    def _parse_docx(self, file_path: str, progress_callback=None) -> list[RawTableData]:
        """Word 解析器占位 — Task 1.3 实现"""
        raise NotImplementedError("Word 解析器尚未实现")

    def _parse_pdf(self, file_path: str, progress_callback=None) -> list[RawTableData]:
        """PDF 解析器占位 — Task 1.4 实现"""
        raise NotImplementedError("PDF 解析器尚未实现")

    @staticmethod
    def _is_ocr_available() -> bool:
        """检测 OCR 模块（PaddleOCR）是否已安装"""
        try:
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    def _fallback_ocr(self, file_path: str, progress_callback=None) -> list[RawTableData]:
        """OCR 降级解析 — Phase 5 实现，当前返回空列表 + 提示"""
        if not self._is_ocr_available():
            return []
        raise NotImplementedError("OCR 解析尚未实现")
```

**设计要点：**
- `parse()` 方法根据文件后缀分发到具体解析器
- `_parse_xlsx()` 使用 `read_only=True, data_only=True` 优化内存和读取公式计算值
- 每个 sheet 生成一个 RawTableData，跳过空白 sheet
- 第一行作为表头，其余行为数据行
- 单元格值统一转为字符串（`str(cell.value)`），None 保留为 None
- `_parse_docx` 和 `_parse_pdf` 当前为占位，抛出 `NotImplementedError`
- `_is_ocr_available()` 和 `_fallback_ocr()` 为 OCR 占位

## 测试与验收

### tests/test_document_parser.py（Excel 部分）

测试文件在测试中用 openpyxl 动态生成，不依赖外部文件。

```python
import pytest
from pathlib import Path


@pytest.fixture
def parser():
    from engines.document_parser import DocumentParser
    return DocumentParser()


@pytest.fixture
def sample_xlsx(tmp_path) -> Path:
    """生成一个包含两个 sheet 的测试 Excel"""
    import openpyxl
    wb = openpyxl.Workbook()
    # Sheet1: 有数据
    ws1 = wb.active
    ws1.title = "报价单"
    ws1.append(["商品名称", "单价", "数量"])
    ws1.append(["笔记本电脑", "4299", "50"])
    ws1.append(["显示器", "1599", "30"])
    # Sheet2: 空白
    ws2 = wb.create_sheet("空白页")
    # Sheet3: 有数据
    ws3 = wb.create_sheet("配件")
    ws3.append(["品名", "价格"])
    ws3.append(["键盘", "199"])

    path = tmp_path / "test.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def empty_xlsx(tmp_path) -> Path:
    """生成一个完全空白的 Excel"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "空白"
    path = tmp_path / "empty.xlsx"
    wb.save(path)
    return path


def test_parse_xlsx_basic(parser, sample_xlsx):
    """解析含数据的 Excel → 跳过空 sheet，返回 2 个表格"""
    results = parser.parse(str(sample_xlsx))
    assert len(results) == 2

    # 第一个表格
    t1 = results[0]
    assert t1.sheet_name == "报价单"
    assert t1.headers == ["商品名称", "单价", "数量"]
    assert t1.row_count == 2
    assert t1.column_count == 3
    assert t1.rows[0] == ["笔记本电脑", "4299", "50"]

    # 第二个表格
    t2 = results[1]
    assert t2.sheet_name == "配件"
    assert t2.row_count == 1


def test_parse_xlsx_empty(parser, empty_xlsx):
    """完全空白的 Excel → 返回空列表"""
    results = parser.parse(str(empty_xlsx))
    assert results == []


def test_parse_xlsx_progress(parser, sample_xlsx):
    """进度回调被正确调用"""
    progress_values = []
    results = parser.parse(str(sample_xlsx), progress_callback=lambda p: progress_values.append(p))
    assert len(progress_values) > 0
    assert progress_values[-1] <= 1.0


def test_parse_unsupported_type(parser, tmp_path):
    """不支持的文件类型 → ValueError"""
    path = tmp_path / "test.txt"
    path.write_text("hello")
    with pytest.raises(ValueError, match="不支持的文件类型"):
        parser.parse(str(path))


def test_parse_xlsx_none_cells(parser, tmp_path):
    """含 None 单元格的 Excel → None 保留"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["A", "B", "C"])
    ws.append(["x", None, "z"])
    path = tmp_path / "sparse.xlsx"
    wb.save(path)

    results = parser.parse(str(path))
    assert len(results) == 1
    assert results[0].rows[0] == ["x", None, "z"]


def test_is_ocr_available(parser):
    """OCR 检测不崩溃"""
    result = parser._is_ocr_available()
    assert isinstance(result, bool)
```

### 门禁检查

```bash
cd backend
ruff check engines/document_parser.py tests/test_document_parser.py
mypy engines/document_parser.py --ignore-missing-imports
pytest tests/test_document_parser.py -x -q
```

**断言清单：**
- 含数据的多 sheet Excel → 跳过空 sheet，返回正确数量的 RawTableData
- 每个 RawTableData 的 sheet_name、headers、rows、row_count、column_count 均正确
- 空白 Excel → 返回空列表
- 不支持的文件类型 → ValueError
- None 单元格 → 保留为 None
- 进度回调被调用且值在 0.0-1.0 范围内
- `_is_ocr_available()` 返回 bool 且不崩溃

## 提交

```bash
git add backend/engines/document_parser.py backend/tests/test_document_parser.py
git commit -m "Phase 1.2: DocumentParser Excel 解析器 — openpyxl 多 sheet 提取 + 空 sheet 跳过"
```
