from __future__ import annotations

from fastapi import APIRouter

from api.deps import get_project_db
from models.comparison import ProblemGroup
from services.problem_service import ProblemService

router = APIRouter(tags=["问题清单"])


@router.get(
    "/projects/{project_id}/problems",
    response_model=list[ProblemGroup],
)
async def get_problems(project_id: str) -> list[ProblemGroup]:
    """获取待处理问题清单"""
    db = get_project_db(project_id)
    service = ProblemService(db)
    return service.get_problems(project_id)
