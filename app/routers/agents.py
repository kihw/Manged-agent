from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from app.routers.errors import ERROR_RESPONSES

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentLimits(BaseModel):
    max_iterations: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_cost_usd: float = Field(ge=0)
    max_duration_sec: int = Field(ge=1)


class AgentApprovalRules(BaseModel):
    require_human_for: list[str] = Field(default_factory=list)


class AgentServer(BaseModel):
    server_id: str
    name: str
    transport: str
    endpoint: str
    status: str


class AgentDefinitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    version: str
    description: str | None = None
    system_prompt: str
    tools: list[str]
    allowed_mcp_servers: list[AgentServer] = Field(default_factory=list)
    policy_profile: str
    limits: AgentLimits
    approval_rules: AgentApprovalRules | None = None


@router.post(
    "",
    response_model=AgentDefinitionPayload,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def upsert_agent(definition: AgentDefinitionPayload) -> AgentDefinitionPayload:
    return definition


@router.get("/{agent_id}", responses=ERROR_RESPONSES)
async def get_agent(agent_id: str) -> dict[str, str]:
    return {"agent_id": agent_id, "message": "placeholder"}
