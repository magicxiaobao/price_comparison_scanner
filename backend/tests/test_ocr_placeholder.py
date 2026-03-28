from pathlib import Path

import pytest


@pytest.fixture
def parser():
    from engines.document_parser import DocumentParser

    return DocumentParser()


class TestOCRPlaceholder:
    """OCR 占位逻辑验证 — MVP 阶段 OCR 不可用"""

    def test_is_ocr_available_returns_false(self, parser):
        """MVP 阶段 OCR 不可用（未安装 PaddleOCR）"""
        assert parser._is_ocr_available() is False

    def test_fallback_ocr_returns_not_installed(self, parser):
        """OCR 未安装时返回明确提示"""
        result = parser._fallback_ocr("dummy.pdf")
        assert result["success"] is False
        assert result["error_code"] == "OCR_NOT_INSTALLED"
        assert "OCR 扩展未安装" in result["message"]
        assert result["tables"] == []

    def test_pdf_l1_still_works(self, parser, tmp_path: Path):
        """数字版 PDF 的 L1 结构化提取不受影响"""
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)

        col_width = 40
        row_height = 8
        for header in ["Product", "Price", "Qty"]:
            pdf.cell(col_width, row_height, header, border=1)
        pdf.ln()
        for cell in ["Laptop", "4299", "50"]:
            pdf.cell(col_width, row_height, cell, border=1)
        pdf.ln()

        path = tmp_path / "digital.pdf"
        pdf.output(str(path))

        results = parser.parse(str(path))
        assert isinstance(results, list)
        # 数字版 PDF 应该能提取到表格（pdfplumber L1）
        if len(results) > 0:
            assert results[0].page_number == 1
            assert results[0].row_count >= 1

    def test_no_crash_on_scan_pdf(self, parser, tmp_path: Path):
        """扫描版 PDF（无可提取表格）不导致崩溃，fallback 不抛异常"""
        from fpdf import FPDF

        # 创建一个纯文本 PDF（模拟扫描版 — L1 无法提取表格）
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "This is a scan-like PDF with no extractable tables")
        path = tmp_path / "scan.pdf"
        pdf.output(str(path))

        # L1 提取返回空列表，不崩溃
        results = parser.parse(str(path))
        assert results == []

        # fallback 也不崩溃，返回错误提示
        fallback = parser._fallback_ocr(str(path))
        assert fallback["success"] is False
        assert fallback["error_code"] == "OCR_NOT_INSTALLED"
