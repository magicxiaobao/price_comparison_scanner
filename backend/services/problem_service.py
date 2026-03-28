from __future__ import annotations

import json

from db.database import Database
from models.comparison import ProblemGroup, ProblemItem


class ProblemService:
    """
    待处理问题清单聚合服务。

    聚合所有未解决问题，按类型分组返回。覆盖 PRD 7.1 定义的全部问题类型：
    - 未确认供应商名称
    - 未映射字段
    - 规则冲突
    - 低置信字段未确认
    - 单位不一致异常
    - 税价口径异常
    - 未确认归组项
    - 必填字段缺失
    - 未确认需求匹配
    - 必选需求未满足
    - 无法判断且未确认的需求项
    - 部分符合但未判定可接受的需求项
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_problems(self, project_id: str) -> list[ProblemGroup]:
        problems: list[ProblemGroup] = []

        collectors: list[tuple[str, str, str, str]] = [
            # (method_name, type, label, stage)
        ]
        _ = collectors  # unused — we call each method explicitly for clarity

        # 1. 未确认供应商名称
        items = self._unconfirmed_suppliers(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unconfirmed_supplier",
                label="未确认供应商名称",
                stage="import",
                count=len(items),
                items=items,
            ))

        # 2. 未映射字段
        items = self._unmapped_fields(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unmapped_field",
                label="未映射字段",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 3. 规则冲突
        items = self._rule_conflicts(project_id)
        if items:
            problems.append(ProblemGroup(
                type="rule_conflict",
                label="规则冲突",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 4. 低置信字段未确认
        items = self._low_confidence_unconfirmed(project_id)
        if items:
            problems.append(ProblemGroup(
                type="low_confidence_unconfirmed",
                label="低置信字段未确认",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 5. 单位不一致异常
        items = self._unit_anomalies(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unit_mismatch",
                label="单位不一致异常",
                stage="comparison",
                count=len(items),
                items=items,
            ))

        # 6. 税价口径异常
        items = self._tax_anomalies(project_id)
        if items:
            problems.append(ProblemGroup(
                type="tax_basis_mismatch",
                label="税价口径异常",
                stage="comparison",
                count=len(items),
                items=items,
            ))

        # 7. 未确认归组项
        items = self._unconfirmed_groups(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unconfirmed_group",
                label="未确认归组项",
                stage="grouping",
                count=len(items),
                items=items,
            ))

        # 8. 必填字段缺失
        items = self._missing_required_fields(project_id)
        if items:
            problems.append(ProblemGroup(
                type="missing_required_field",
                label="必填字段缺失",
                stage="normalize",
                count=len(items),
                items=items,
            ))

        # 9. 未确认需求匹配
        items = self._unconfirmed_compliance(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unconfirmed_compliance",
                label="未确认需求匹配",
                stage="compliance",
                count=len(items),
                items=items,
            ))

        # 10. 必选需求未满足
        items = self._mandatory_not_met(project_id)
        if items:
            problems.append(ProblemGroup(
                type="mandatory_not_met",
                label="必选需求未满足",
                stage="compliance",
                count=len(items),
                items=items,
                severity="error",
            ))

        # 11. 无法判断且未确认
        items = self._unclear_unconfirmed(project_id)
        if items:
            problems.append(ProblemGroup(
                type="unclear_unconfirmed",
                label="无法判断且未确认",
                stage="compliance",
                count=len(items),
                items=items,
            ))

        # 12. 部分符合但未判定可接受
        items = self._partial_not_decided(project_id)
        if items:
            problems.append(ProblemGroup(
                type="partial_not_decided",
                label="部分符合但未判定可接受",
                stage="compliance",
                count=len(items),
                items=items,
            ))

        return problems

    # ---- 查询方法 ----

    def _unconfirmed_suppliers(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT id, original_filename FROM supplier_files
                   WHERE project_id = ? AND (supplier_name = '' OR supplier_confirmed = 0)""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="import",
                    target_id=row[0],
                    description=f"文件「{row[1]}」的供应商名称未确认",
                )
                for row in cursor.fetchall()
            ]

    def _unmapped_fields(self, project_id: str) -> list[ProblemItem]:
        """
        [C4-fix] 用 column_mapping JSON 判断：值为 null 或空字符串的 key 即为未映射。
        """
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sr.column_mapping FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ? AND sr.column_mapping IS NOT NULL""",
                (project_id,),
            )
            items: list[ProblemItem] = []
            for row in cursor.fetchall():
                mapping: dict[str, str | None] = json.loads(row[2] or "{}")
                unmapped = [k for k, v in mapping.items() if not v]
                if unmapped:
                    items.append(ProblemItem(
                        id=row[0],
                        stage="normalize",
                        target_id=row[0],
                        description=f"行「{row[1] or '未知'}」存在未映射字段: {', '.join(unmapped)}",
                    ))
            return items

    def _rule_conflicts(self, project_id: str) -> list[ProblemItem]:
        """
        [C4-fix] 用 hit_rule_snapshots JSON 判断：同一 target_field 出现 >1 次视为冲突。
        """
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sr.hit_rule_snapshots FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ? AND sr.hit_rule_snapshots IS NOT NULL""",
                (project_id,),
            )
            items: list[ProblemItem] = []
            for row in cursor.fetchall():
                snapshots: list[dict[str, str]] = json.loads(row[2] or "[]")
                fields_hit: dict[str, int] = {}
                for s in snapshots:
                    tf = s.get("target_field", "")
                    if tf:
                        fields_hit[tf] = fields_hit.get(tf, 0) + 1
                conflicts = [f for f, c in fields_hit.items() if c > 1]
                if conflicts:
                    items.append(ProblemItem(
                        id=row[0],
                        stage="normalize",
                        target_id=row[0],
                        description=f"行「{row[1] or '未知'}」存在规则冲突: {', '.join(conflicts)}",
                    ))
            return items

    def _low_confidence_unconfirmed(self, project_id: str) -> list[ProblemItem]:
        """
        [C4-fix] confidence < 0.8 且 needs_review = 1 且 is_manually_modified = 0。
        """
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sr.confidence FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ? AND sr.confidence < 0.8
                     AND sr.needs_review = 1 AND sr.is_manually_modified = 0""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="normalize",
                    target_id=row[0],
                    description=f"行「{row[1] or '未知'}」置信度 {row[2]:.0%}，未确认",
                )
                for row in cursor.fetchall()
            ]

    def _unit_anomalies(self, project_id: str) -> list[ProblemItem]:
        return self._get_anomalies_by_type(project_id, "unit_mismatch")

    def _tax_anomalies(self, project_id: str) -> list[ProblemItem]:
        return self._get_anomalies_by_type(project_id, "tax_basis_mismatch")

    def _get_anomalies_by_type(
        self, project_id: str, anomaly_type: str
    ) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cr.id, cr.group_id, cr.anomaly_details, cg.group_name
                   FROM comparison_results cr
                   JOIN commodity_groups cg ON cg.id = cr.group_id
                   WHERE cr.project_id = ? AND cr.has_anomaly = 1""",
                (project_id,),
            )
            items: list[ProblemItem] = []
            for row in cursor.fetchall():
                details: list[dict[str, object]] = json.loads(row[2] or "[]")
                for d in details:
                    if d.get("type") == anomaly_type:
                        items.append(ProblemItem(
                            id=row[0],
                            stage="comparison",
                            target_id=row[1],
                            description=f"商品组「{row[3]}」: {d.get('description', '')}",
                            severity="error",
                        ))
            return items

    def _unconfirmed_groups(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT id, group_name FROM commodity_groups
                   WHERE project_id = ? AND status = 'candidate'""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="grouping",
                    target_id=row[0],
                    description=f"归组「{row[1]}」待确认",
                )
                for row in cursor.fetchall()
            ]

    def _missing_required_fields(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT sr.id, sr.product_name, sf.supplier_name FROM standardized_rows sr
                   JOIN raw_tables rt ON rt.id = sr.raw_table_id
                   JOIN supplier_files sf ON sf.id = rt.supplier_file_id
                   WHERE sf.project_id = ?
                     AND (sr.product_name IS NULL OR sr.product_name = ''
                          OR sr.unit IS NULL OR sr.unit = ''
                          OR sr.unit_price IS NULL)""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="normalize",
                    target_id=row[0],
                    description=f"{row[2]} 行「{row[1] or '未知'}」缺失必填字段",
                )
                for row in cursor.fetchall()
            ]

    def _unconfirmed_compliance(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND cm.needs_review = 1""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="compliance",
                    target_id=row[0],
                    description=f"需求「{row[1]}」× 供应商「{row[2]}」待确认",
                )
                for row in cursor.fetchall()
            ]

    def _mandatory_not_met(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND ri.is_mandatory = 1
                     AND cm.status = 'no_match'""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="compliance",
                    target_id=row[0],
                    description=f"必选需求「{row[1]}」× 供应商「{row[2]}」不符合",
                    severity="error",
                )
                for row in cursor.fetchall()
            ]

    def _unclear_unconfirmed(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND cm.status = 'unclear'
                     AND cm.needs_review = 1""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="compliance",
                    target_id=row[0],
                    description=f"需求「{row[1]}」× 供应商「{row[2]}」无法判断，待确认",
                )
                for row in cursor.fetchall()
            ]

    def _partial_not_decided(self, project_id: str) -> list[ProblemItem]:
        with self.db.read() as conn:
            cursor = conn.execute(
                """SELECT cm.id, ri.title, sf.supplier_name
                   FROM compliance_matches cm
                   JOIN requirement_items ri ON ri.id = cm.requirement_item_id
                   JOIN supplier_files sf ON sf.id = cm.supplier_file_id
                   WHERE ri.project_id = ? AND cm.status = 'partial'
                     AND cm.is_acceptable = 0 AND cm.needs_review = 1""",
                (project_id,),
            )
            return [
                ProblemItem(
                    id=row[0],
                    stage="compliance",
                    target_id=row[0],
                    description=f"需求「{row[1]}」× 供应商「{row[2]}」部分符合，未判定可接受",
                )
                for row in cursor.fetchall()
            ]
