# Task 5.3: OCR 接口占位验证 + 未安装时用户提示

## 输入条件

- Phase 1 的 DocumentParser 已实现，包含 `_is_ocr_available()` 方法和 `_fallback_ocr()` 方法
- PDF L1 结构化提取已可用（Phase 1 Task 1.4）
- 前端 ImportStage 已实现文件上传和解析进度显示

## 输出物

- 修改: `backend/engines/document_parser.py`（确认 OCR 占位逻辑正确，补充用户提示消息）
- 创建: `backend/tests/test_ocr_placeholder.py`（OCR 占位路径测试）
- 修改: `frontend/src/components/stages/import-stage.tsx`（添加 OCR 未安装提示 UI，若尚未有）

## 禁止修改

- 不修改 `backend/services/` 目录
- 不修改 `backend/db/` 目录
- 不安装 PaddleOCR / PaddlePaddle 依赖
- 不修改 `backend/requirements.txt`（不引入 OCR 依赖）
- 不修改其他引擎文件

## 实现规格

### 后端 OCR 占位逻辑确认

确认 `backend/engines/document_parser.py` 中以下逻辑正确：

```python
class DocumentParser:
    def _is_ocr_available(self) -> bool:
        """检测 OCR 扩展是否已安装。MVP 阶段始终返回 False。"""
        try:
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    def _fallback_ocr(self, file_path: str) -> dict:
        """OCR 降级处理。当 L1 结构化提取失败时调用。"""
        if not self._is_ocr_available():
            return {
                "success": False,
                "error_code": "OCR_NOT_INSTALLED",
                "message": "OCR 扩展未安装。请安装 OCR 扩展包以支持扫描版 PDF 解析，"
                           "或将文件内容手动复制到 Excel 后重新导入。",
                "tables": [],
            }
        # OCR 实际处理逻辑（后续版本实现）
        ...
```

### PDF 解析降级链路

确认 PDF 解析流程中的降级逻辑：

```
1. 尝试 L1 结构化提取（pdfplumber）
2. L1 提取到表格 → 返回结果
3. L1 未提取到表格 → 调用 _fallback_ocr()
4. _fallback_ocr() 返回 OCR_NOT_INSTALLED 错误
5. 前端收到错误 → 显示用户提示
```

### 前端 OCR 未安装提示

当文件解析返回 `error_code: "OCR_NOT_INSTALLED"` 时：

```tsx
// 在 ImportStage 中处理 OCR 未安装的情况
// 显示提示卡片：
// - 标题：「OCR 扩展未安装」
// - 说明：「当前文件为扫描版 PDF，需要 OCR 扩展才能自动识别表格内容。」
// - 建议操作：
//   1. 「安装 OCR 扩展」— 链接到帮助文档（MVP 阶段显示文字说明即可）
//   2. 「手动处理」— 提示用户将文件内容复制到 Excel 后重新导入
// - 样式：信息蓝色背景，非阻断性提示
```

### 关键约束

- OCR 占位**只做能力检测和提示**，不做实际 OCR 集成
- `_is_ocr_available()` 在 MVP 阶段始终返回 `False`（因为不安装 PaddleOCR）
- 不能因为 OCR 不可用而导致应用崩溃或异常退出
- 非扫描版 PDF（数字版）不受影响，仍走 L1 结构化提取

## 测试与验收

### 后端测试

```python
# backend/tests/test_ocr_placeholder.py

class TestOCRPlaceholder:
    def test_is_ocr_available_returns_false(self):
        """MVP 阶段 OCR 不可用"""
        parser = DocumentParser()
        assert parser._is_ocr_available() is False

    def test_fallback_ocr_returns_not_installed(self):
        """OCR 未安装时返回明确提示"""
        parser = DocumentParser()
        result = parser._fallback_ocr("dummy.pdf")
        assert result["success"] is False
        assert result["error_code"] == "OCR_NOT_INSTALLED"
        assert "OCR 扩展未安装" in result["message"]
        assert result["tables"] == []

    def test_pdf_l1_still_works(self):
        """数字版 PDF 的 L1 结构化提取不受影响"""
        # 使用测试用的简单数字版 PDF fixture
        # 确认 L1 提取正常返回表格数据
        ...

    def test_no_crash_on_scan_pdf(self):
        """扫描版 PDF 不导致崩溃"""
        # 使用一个空白 PDF 或纯图片 PDF
        # 确认返回错误信息而非抛出异常
        ...
```

### 门禁检查

```bash
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest tests/test_ocr_placeholder.py -v

cd frontend
pnpm lint
pnpm tsc --noEmit
```

### 手动验证

```
1. 上传数字版 PDF → 正常解析出表格（L1 路径）
2. 上传扫描版 PDF（或纯图片 PDF）→ L1 失败 → 显示 OCR 未安装提示
3. 提示信息可读，不阻断其他操作
4. 应用不崩溃，其他文件上传不受影响
```

## 提交

```bash
git add backend/engines/document_parser.py backend/tests/test_ocr_placeholder.py frontend/src/components/stages/import-stage.tsx
git commit -m "Phase 5.3: OCR 接口占位验证 + 未安装时用户提示"
```
