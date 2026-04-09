from fastapi import APIRouter, status

from app.models import AgentDefinition
from app.routers.errors import ERROR_RESPONSES

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post(
    "",
    response_model=AgentDefinition,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def upsert_agent(definition: AgentDefinition) -> AgentDefinition:
    return definition


@router.get("/{agent_id}", response_model=dict[str, str], responses=ERROR_RESPONSES)
async def get_agent(agent_id: str) -> dict[str, str]:
    return {"agent_id": agent_id, "message": "placeholder"}
