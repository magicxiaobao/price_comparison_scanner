from pydantic import BaseModel, Field


class StageStatuses(BaseModel):
    import_status: str = "pending"  # pending | completed | dirty
    normalize_status: str = "pending"
    grouping_status: str = "pending"
    compliance_status: str = "skipped"  # skipped | pending | completed | dirty
    comparison_status: str = "pending"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    supplier_count: int = 0
    current_stage: str = "导入文件"


class ProjectDetail(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    stage_statuses: StageStatuses
