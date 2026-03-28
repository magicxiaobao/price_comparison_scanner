from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedRequirement:
    """从 Excel 模板解析出的需求项"""

    code: str | None
    category: str
    title: str
    description: str | None
    is_mandatory: bool
    match_type: str
    expected_value: str | None
    operator: str | None


class ComplianceEvaluator:
    """需求标准管理 + 供应商符合性匹配引擎（可选模块）

    本 Task 仅实现 CRUD + 导入导出部分，匹配逻辑在 Task 4.2。
    """

    # ---- 导入解析 ----

    def parse_requirements_excel(self, file_path: str) -> list[ParsedRequirement]:
        """从模板 Excel 导入需求标准。

        模板格式：
        | 需求编号 | 需求分类 | 需求标题 | 需求描述 | 是否必选 | 判断类型 | 目标值 | 比较操作符 |
        """
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True)
        ws = wb.active
        results: list[ParsedRequirement] = []

        header_row = 1
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not row or not row[2]:  # title 列为空则跳过
                continue
            code = str(row[0]).strip() if row[0] else None
            category = str(row[1]).strip() if row[1] else "功能要求"
            title = str(row[2]).strip()
            description = str(row[3]).strip() if row[3] else None
            is_mandatory = (
                str(row[4]).strip() in ("是", "必选", "1", "true", "True")
                if row[4]
                else True
            )
            match_type = str(row[5]).strip().lower() if row[5] else "manual"
            if match_type not in ("keyword", "numeric", "manual"):
                match_type = "manual"
            expected_value = str(row[6]).strip() if row[6] else None
            operator = (
                str(row[7]).strip().lower() if len(row) > 7 and row[7] else None
            )
            if operator and operator not in ("gte", "lte", "eq", "range"):
                operator = None

            results.append(
                ParsedRequirement(
                    code=code,
                    category=(
                        category
                        if category
                        in ("功能要求", "技术规格", "商务条款", "服务要求", "交付要求")
                        else "功能要求"
                    ),
                    title=title,
                    description=description,
                    is_mandatory=is_mandatory,
                    match_type=match_type,
                    expected_value=expected_value,
                    operator=operator,
                )
            )

        wb.close()
        return results

    def export_requirements_template(
        self, requirements: list[dict], output_path: str
    ) -> str:
        """导出需求标准为 Excel 模板。"""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "需求标准"

        headers = [
            "需求编号", "需求分类", "需求标题", "需求描述",
            "是否必选", "判断类型", "目标值", "比较操作符",
        ]
        ws.append(headers)

        for req in requirements:
            ws.append([
                req.get("code", ""),
                req.get("category", ""),
                req.get("title", ""),
                req.get("description", ""),
                "是" if req.get("is_mandatory", True) else "否",
                req.get("match_type", ""),
                req.get("expected_value", ""),
                req.get("operator", ""),
            ])

        wb.save(output_path)
        return output_path

    # ---- 匹配逻辑在 Task 4.2 中实现 ----
