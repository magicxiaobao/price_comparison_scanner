# Task 4.6: ReportGenerator — 4 Sheet Excel 导出

## 输入条件

- Task 4.3 完成（符合性 API 可用）
- Task 4.5 完成（比价 API 可用）
- 标准化数据、归组数据、比价结果数据均可用

## 输出物

- 创建: `backend/engines/report_generator.py`
- 创建: `backend/services/report_service.py`
- 创建: `backend/api/export.py`
- 修改: `backend/main.py`（注册 export 路由）
- 创建: `backend/tests/test_report_generator.py`
- 创建: `backend/tests/test_export_api.py`

## 禁止修改

- 不修改 `backend/db/schema.sql`
- 不修改已有引擎、repo、service 文件
- 不修改 `frontend/`

## 实现规格

> **MCP 强制规则**：首次使用 openpyxl 写入 + 样式 API（PatternFill, Font, Alignment, Border, NamedStyle）时，**必须用 Context7 查文档确认用法**。

### engines/report_generator.py

```python
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone


class ReportGenerator:
    """4 Sheet Excel 导出引擎"""

    ENGINE_VERSION = "report_generator:1.0"

    def export_to_excel(
        self,
        output_path: str,
        comparison_results: list[dict],
        standardized_rows: list[dict],
        traceability_data: list[dict],
        compliance_matrix: Optional[dict],
        supplier_names: dict[str, str],
    ) -> str:
        """
        生成 Excel 审计底稿。

        Sheet 1: 比价结果表
        Sheet 2: 标准化明细表
        Sheet 3: 追溯信息表
        Sheet 4: 需求符合性矩阵（仅当 compliance_matrix 非 None）

        输入数据契约（最小必需字段）：
        - comparison_results[]: group_id, group_name, comparison_status, supplier_prices[],
          min_price, effective_min_price, has_anomaly, anomaly_details[]
        - comparison_results[].supplier_prices[]: supplier_name, unit_price, total_price, tax_basis, unit
        - standardized_rows[]: id, product_name, spec_model, unit, quantity, unit_price, total_price,
          supplier_file_id, source_location
        - traceability_data[]: standardized_row_id, supplier_name, original_filename,
          source_location (JSON), hit_rule_snapshots (JSON)
        - compliance_matrix (Optional): supplier_names[], rows[].requirement, rows[].suppliers{}
        - supplier_names: {supplier_file_id: supplier_name}

        注意：首次使用 openpyxl 写入+样式 API，必须用 Context7 查文档。
        """
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

        wb = openpyxl.Workbook()

        # ---- 样式定义 ----
        header_font = Font(bold=True, size=11)
        header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        min_price_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # 绿色
        effective_min_fill = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")  # 蓝色
        anomaly_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")  # 红色
        partial_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # 黄色
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        # ---- Sheet 1: 比价结果表 ----
        ws1 = wb.active
        ws1.title = "比价结果表"
        self._write_comparison_sheet(ws1, comparison_results, supplier_names,
                                     compliance_matrix is not None,
                                     header_font, header_fill, min_price_fill,
                                     effective_min_fill, anomaly_fill, thin_border)

        # ---- Sheet 2: 标准化明细表 ----
        ws2 = wb.create_sheet("标准化明细表")
        self._write_standardized_sheet(ws2, standardized_rows, supplier_names,
                                       header_font, header_fill, thin_border)

        # ---- Sheet 3: 追溯信息表 ----
        ws3 = wb.create_sheet("追溯信息表")
        self._write_traceability_sheet(ws3, traceability_data, supplier_names,
                                       header_font, header_fill, thin_border)

        # ---- Sheet 4: 需求符合性矩阵（可选） ----
        if compliance_matrix is not None:
            ws4 = wb.create_sheet("需求符合性矩阵")
            self._write_compliance_sheet(ws4, compliance_matrix, supplier_names,
                                         header_font, header_fill, partial_fill, thin_border)

        # 保存
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return output_path

    def _write_comparison_sheet(
        self, ws, results, supplier_names, has_compliance,
        header_font, header_fill, min_fill, eff_fill, anomaly_fill, border
    ):
        """Sheet 1: 比价结果表"""
        # 表头
        headers = ["商品组", "比较状态"]
        sorted_sids = sorted(supplier_names.keys())
        for sid in sorted_sids:
            headers.append(f"{supplier_names[sid]} 单价")
        headers.extend(["全量最低价", "有效最低价", "最高价", "平均价", "差额", "异常标记"])
        if has_compliance:
            headers.append("符合性摘要")

        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        # 数据行
        for row_idx, r in enumerate(results, 2):
            ws.cell(row=row_idx, column=1, value=r.get("group_name", "")).border = border
            ws.cell(row=row_idx, column=2, value=r.get("comparison_status", "")).border = border

            supplier_prices = json.loads(r.get("supplier_prices", "[]"))
            sp_map = {sp["supplier_file_id"]: sp for sp in supplier_prices}
            for col_offset, sid in enumerate(sorted_sids):
                sp = sp_map.get(sid, {})
                cell = ws.cell(row=row_idx, column=3 + col_offset, value=sp.get("unit_price"))
                cell.border = border
                # 全量最低价高亮
                if sp.get("unit_price") is not None and sp.get("unit_price") == r.get("min_price"):
                    cell.fill = min_fill
                # 有效最低价高亮
                if (has_compliance and sp.get("unit_price") is not None
                        and sp.get("unit_price") == r.get("effective_min_price")):
                    cell.fill = eff_fill

            base_col = 3 + len(sorted_sids)
            ws.cell(row=row_idx, column=base_col, value=r.get("min_price")).border = border
            ws.cell(row=row_idx, column=base_col + 1, value=r.get("effective_min_price")).border = border
            ws.cell(row=row_idx, column=base_col + 2, value=r.get("max_price")).border = border
            ws.cell(row=row_idx, column=base_col + 3, value=r.get("avg_price")).border = border
            ws.cell(row=row_idx, column=base_col + 4, value=r.get("price_diff")).border = border

            # 异常标记
            anomalies = json.loads(r.get("anomaly_details", "[]"))
            anomaly_text = "; ".join(a["description"] for a in anomalies) if anomalies else ""
            anomaly_cell = ws.cell(row=row_idx, column=base_col + 5, value=anomaly_text)
            anomaly_cell.border = border
            if anomalies:
                anomaly_cell.fill = anomaly_fill

    def _write_standardized_sheet(self, ws, rows, supplier_names, header_font, header_fill, border):
        """Sheet 2: 标准化明细表"""
        headers = ["供应商", "商品名称", "规格型号", "单位", "数量", "单价", "总价",
                    "税率", "税价口径", "备注", "是否人工修改"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        for row_idx, r in enumerate(rows, 2):
            ws.cell(row=row_idx, column=1, value=r.get("supplier_name", "")).border = border
            ws.cell(row=row_idx, column=2, value=r.get("product_name", "")).border = border
            ws.cell(row=row_idx, column=3, value=r.get("spec_model", "")).border = border
            ws.cell(row=row_idx, column=4, value=r.get("unit", "")).border = border
            ws.cell(row=row_idx, column=5, value=r.get("quantity")).border = border
            ws.cell(row=row_idx, column=6, value=r.get("unit_price")).border = border
            ws.cell(row=row_idx, column=7, value=r.get("total_price")).border = border
            ws.cell(row=row_idx, column=8, value=r.get("tax_rate")).border = border
            ws.cell(row=row_idx, column=9, value=r.get("tax_basis", "")).border = border
            ws.cell(row=row_idx, column=10, value=r.get("remark", "")).border = border
            ws.cell(row=row_idx, column=11, value="是" if r.get("is_manually_modified") else "否").border = border

    def _write_traceability_sheet(self, ws, data, supplier_names, header_font, header_fill, border):
        """Sheet 3: 追溯信息表"""
        headers = ["来源文件名", "供应商", "来源定位", "原始列名", "原始值",
                    "标准字段名", "标准化后值", "命中规则", "匹配方式",
                    "识别方式", "置信度", "是否人工确认", "是否人工修改"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        for row_idx, r in enumerate(data, 2):
            for col_idx, key in enumerate([
                "source_file", "supplier_name", "source_location",
                "original_column", "original_value", "standard_field",
                "standardized_value", "hit_rule", "match_mode",
                "extraction_mode", "confidence", "is_confirmed", "is_modified",
            ], 1):
                ws.cell(row=row_idx, column=col_idx, value=str(r.get(key, ""))).border = border

    def _write_compliance_sheet(self, ws, matrix, supplier_names, header_font, header_fill, partial_fill, border):
        """Sheet 4: 需求符合性矩阵"""
        sorted_sids = sorted(supplier_names.keys())

        # 表头
        base_headers = ["需求编号", "需求分类", "需求描述", "是否必选"]
        for sid in sorted_sids:
            name = supplier_names[sid]
            base_headers.append(f"{name} 状态")
            base_headers.append(f"{name} 证据摘要")
        base_headers.append("是否人工确认")

        for col_idx, h in enumerate(base_headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        # 数据行
        rows = matrix.get("rows", [])
        for row_idx, mr in enumerate(rows, 2):
            req = mr.get("requirement", {})
            ws.cell(row=row_idx, column=1, value=req.get("code", "")).border = border
            ws.cell(row=row_idx, column=2, value=req.get("category", "")).border = border
            ws.cell(row=row_idx, column=3, value=req.get("title", "")).border = border
            ws.cell(row=row_idx, column=4, value="是" if req.get("is_mandatory") else "否").border = border

            suppliers = mr.get("suppliers", {})
            col_offset = 5
            any_confirmed = False
            for sid in sorted_sids:
                cell_data = suppliers.get(sid, {})
                status = cell_data.get("status", "")
                evidence = cell_data.get("evidence_text", "")
                status_cell = ws.cell(row=row_idx, column=col_offset, value=status)
                status_cell.border = border
                if status == "partial":
                    status_cell.fill = partial_fill
                ws.cell(row=row_idx, column=col_offset + 1, value=evidence or "").border = border
                col_offset += 2
                if not cell_data.get("needs_review", True):
                    any_confirmed = True

            ws.cell(row=row_idx, column=col_offset, value="是" if any_confirmed else "否").border = border
```

### services/report_service.py

```python
import json
from pathlib import Path
from db.database import Database
from engines.report_generator import ReportGenerator
from models.comparison import ExportResult


class ReportService:
    """导出业务编排"""

    def __init__(self, db: Database):
        self.db = db
        self.engine = ReportGenerator()

    def export_report(self, project_id: str, output_dir: str) -> ExportResult:
        """
        生成 Excel 审计底稿。

        1. 收集比价结果
        2. 收集标准化数据
        3. 收集追溯信息
        4. 检查是否有需求标准 → 收集符合性矩阵
        5. 调用 ReportGenerator
        6. 返回导出结果
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"比价审计底稿_{timestamp}.xlsx"
        output_path = str(Path(output_dir) / file_name)

        comparison_results = self._get_comparison_results(project_id)
        standardized_rows = self._get_standardized_rows(project_id)
        traceability_data = self._get_traceability_data(project_id)
        supplier_names = self._get_supplier_names(project_id)

        compliance_matrix = None
        if self._has_requirements(project_id):
            compliance_matrix = self._get_compliance_matrix_data(project_id)

        self.engine.export_to_excel(
            output_path=output_path,
            comparison_results=comparison_results,
            standardized_rows=standardized_rows,
            traceability_data=traceability_data,
            compliance_matrix=compliance_matrix,
            supplier_names=supplier_names,
        )

        sheet_count = 4 if compliance_matrix else 3
        return ExportResult(file_path=output_path, file_name=file_name, sheet_count=sheet_count)

    # ---- 数据收集 ----

    def _get_comparison_results(self, project_id: str) -> list[dict]:
        from db.comparison_repo import ComparisonRepo
        repo = ComparisonRepo(self.db)
        results = repo.list_by_project(project_id)
        # 附加 group_name
        for r in results:
            group = self._get_group(r["group_id"])
            r["group_name"] = group.get("group_name", "") if group else ""
        return results

    def _get_standardized_rows(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sf.supplier_name
                   FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ?
                   ORDER BY sf.supplier_name""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_traceability_data(self, project_id: str) -> list[dict]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.*, sf.supplier_name, sf.file_name as source_file
                   FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ?""",
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_supplier_names(self, project_id: str) -> dict[str, str]:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT id, supplier_name FROM supplier_files WHERE project_id = ?",
                (project_id,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def _has_requirements(self, project_id: str) -> bool:
        with self.db.read() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM requirement_items WHERE project_id = ?",
                (project_id,),
            )
            return cursor.fetchone()[0] > 0

    def _get_compliance_matrix_data(self, project_id: str) -> dict:
        from services.compliance_service import ComplianceService
        service = ComplianceService(self.db)
        matrix = service.get_matrix(project_id)
        return matrix.model_dump()

    def _get_group(self, group_id: str) -> dict | None:
        with self.db.read() as conn:
            cursor = conn.execute("SELECT * FROM commodity_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
```

### api/export.py

```python
from fastapi import APIRouter
from fastapi.responses import FileResponse
from models.comparison import ExportResponse
from services.report_service import ReportService
from api.deps import get_project_db, get_app_data_dir

router = APIRouter(tags=["导出"])


@router.post("/projects/{project_id}/export", response_model=ExportResponse)
async def export_report(project_id: str):
    """导出 Excel 审计底稿（异步任务）"""
    from services.task_manager import task_manager
    app_data = get_app_data_dir()
    output_dir = str(app_data / "projects" / project_id / "exports")

    db = get_project_db(project_id)
    service = ReportService(db)

    task_id = task_manager.submit(
        task_type="export",
        params={"project_id": project_id},
        callback=lambda: service.export_report(project_id, output_dir),
    )
    return ExportResponse(task_id=task_id)
```

### main.py 修改

```python
from api.export import router as export_router
app.include_router(export_router, prefix="/api")
```

## 测试与验收

### tests/test_report_generator.py

```python
import pytest
import tempfile
import os


class TestReportGenerator:
    def test_export_3_sheets_no_compliance(self, tmp_path):
        """无需求标准时生成 3 个 Sheet"""
        from engines.report_generator import ReportGenerator
        import openpyxl

        engine = ReportGenerator()
        output = str(tmp_path / "test_report.xlsx")
        engine.export_to_excel(
            output_path=output,
            comparison_results=[{
                "group_name": "ThinkPad E14",
                "comparison_status": "comparable",
                "supplier_prices": '[{"supplier_file_id":"sf1","supplier_name":"联想","unit_price":4299}]',
                "min_price": 4299, "effective_min_price": 4299,
                "max_price": 4299, "avg_price": 4299, "price_diff": 0,
                "anomaly_details": "[]",
            }],
            standardized_rows=[{
                "supplier_name": "联想", "product_name": "ThinkPad E14",
                "spec_model": "i5/16GB/512GB", "unit": "台", "quantity": 10,
                "unit_price": 4299, "total_price": 42990,
            }],
            traceability_data=[{
                "source_file": "联想报价.xlsx", "supplier_name": "联想",
                "source_location": "A3", "standard_field": "product_name",
            }],
            compliance_matrix=None,
            supplier_names={"sf1": "联想"},
        )

        assert os.path.exists(output)
        wb = openpyxl.load_workbook(output)
        assert len(wb.sheetnames) == 3
        assert "比价结果表" in wb.sheetnames
        assert "标准化明细表" in wb.sheetnames
        assert "追溯信息表" in wb.sheetnames

    def test_export_4_sheets_with_compliance(self, tmp_path):
        """有需求标准时生成 4 个 Sheet"""
        from engines.report_generator import ReportGenerator
        import openpyxl

        engine = ReportGenerator()
        output = str(tmp_path / "test_report.xlsx")
        engine.export_to_excel(
            output_path=output,
            comparison_results=[],
            standardized_rows=[],
            traceability_data=[],
            compliance_matrix={
                "supplier_names": {"sf1": "联想"},
                "rows": [{
                    "requirement": {"code": "REQ-001", "category": "技术规格",
                                    "title": "内存>=16GB", "is_mandatory": True},
                    "suppliers": {"sf1": {"status": "match", "evidence_text": "16GB DDR5",
                                          "needs_review": False}},
                }],
            },
            supplier_names={"sf1": "联想"},
        )

        wb = openpyxl.load_workbook(output)
        assert len(wb.sheetnames) == 4
        assert "需求符合性矩阵" in wb.sheetnames

    def test_comparison_sheet_has_headers(self, tmp_path):
        """比价结果表包含正确表头"""
        from engines.report_generator import ReportGenerator
        import openpyxl

        engine = ReportGenerator()
        output = str(tmp_path / "test.xlsx")
        engine.export_to_excel(
            output_path=output,
            comparison_results=[],
            standardized_rows=[],
            traceability_data=[],
            compliance_matrix=None,
            supplier_names={"sf1": "联想", "sf2": "戴尔"},
        )

        wb = openpyxl.load_workbook(output)
        ws = wb["比价结果表"]
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "商品组" in headers
        assert "全量最低价" in headers
        assert "异常标记" in headers

    def test_min_price_highlighted(self, tmp_path):
        """最低价单元格应有绿色填充"""
        from engines.report_generator import ReportGenerator
        import openpyxl

        engine = ReportGenerator()
        output = str(tmp_path / "test.xlsx")
        engine.export_to_excel(
            output_path=output,
            comparison_results=[{
                "group_name": "test",
                "comparison_status": "comparable",
                "supplier_prices": '[{"supplier_file_id":"sf1","supplier_name":"A","unit_price":100},{"supplier_file_id":"sf2","supplier_name":"B","unit_price":200}]',
                "min_price": 100, "effective_min_price": 100,
                "max_price": 200, "avg_price": 150, "price_diff": 100,
                "anomaly_details": "[]",
            }],
            standardized_rows=[],
            traceability_data=[],
            compliance_matrix=None,
            supplier_names={"sf1": "A", "sf2": "B"},
        )

        wb = openpyxl.load_workbook(output)
        ws = wb["比价结果表"]
        # 找到最低价单元格（A 供应商，100）
        # 第 2 行，第 3 列（sf1 排序后第一个）
        cell = ws.cell(row=2, column=3)
        assert cell.value == 100
        assert cell.fill.start_color.rgb is not None  # 有填充色
```

### tests/test_export_api.py

```python
import pytest


class TestExportAPI:
    @pytest.mark.anyio
    async def test_export_returns_task_id(self, client_with_comparison, project_id):
        resp = await client_with_comparison.post(
            f"/api/projects/{project_id}/export",
        )
        assert resp.status_code == 200
        assert "task_id" in resp.json()
```

### 门禁命令

```bash
cd backend
ruff check engines/report_generator.py services/report_service.py api/export.py
mypy engines/report_generator.py services/report_service.py api/export.py --ignore-missing-imports
pytest tests/test_report_generator.py tests/test_export_api.py -v -x
```

**断言清单：**

| 断言 | 预期 |
|------|------|
| 无需求标准 → 3 个 Sheet | sheetnames 长度 == 3 |
| 有需求标准 → 4 个 Sheet | 包含「需求符合性矩阵」 |
| 比价结果表有正确表头 | 商品组/全量最低价/异常标记 |
| 最低价单元格有绿色填充 | fill 非空 |
| POST export → task_id | 200 |
| 生成文件存在 | os.path.exists |

## 提交

```bash
git add backend/engines/report_generator.py backend/services/report_service.py \
       backend/api/export.py backend/main.py \
       backend/tests/test_report_generator.py backend/tests/test_export_api.py
git commit -m "Phase 4.6: ReportGenerator — 4 Sheet Excel 导出（比价结果/标准化/追溯/符合性矩阵）+ 条件格式"
```

## Review Notes（审查发现的 Medium/Low 问题）

### 实现约束（开发时必须处理）

- **[C12 关联] `_write_comparison_sheet` 数据格式**：ReportGenerator 从 DB 直接读取 comparison_results 行，`supplier_prices` 是 JSON 字符串需 `json.loads`。但经过 C12 修复后 JSON 中已包含 `tax_basis` 和 `unit` 字段，可直接读取。

### Reviewer 提醒

- **[Low] `_write_traceability_sheet` 追溯字段**：追溯表使用 `is_confirmed` / `is_modified` key，但 standardized_rows 表实际字段名是 `is_manually_modified`。实现时须确保 `_get_traceability_data` 返回的 dict key 与追溯表列 key 映射正确（可在 SQL 查询中用 AS 别名）。
- **[Low] ExportResponse vs ExportResult 命名**：两个模型职责分离正确 —— ExportResponse 用于异步任务提交响应，ExportResult 用于任务完成后的结果。无需修改。
