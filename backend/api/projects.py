from fastapi import APIRouter, HTTPException

from models.project import ProjectCreate, ProjectDetail, ProjectSummary
from services.project_service import ProjectService

router = APIRouter(tags=["项目管理"])
service = ProjectService()


@router.post("/projects", response_model=ProjectDetail)
async def create_project(req: ProjectCreate) -> ProjectDetail:
    return service.create_project(req)


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects() -> list[ProjectSummary]:
    return service.list_projects()


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str) -> ProjectDetail:
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, str]:
    deleted = service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"detail": "已删除"}
