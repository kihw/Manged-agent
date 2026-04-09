from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, str]:
    return {"agent_id": agent_id, "message": "placeholder"}
