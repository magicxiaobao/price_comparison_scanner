from fastapi import APIRouter

router = APIRouter(tags=["系统"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
