from fastapi import APIRouter

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("/{task_id}")
async def get_task_traces(task_id: str) -> dict[str, str]:
    return {"task_id": task_id, "message": "placeholder"}
