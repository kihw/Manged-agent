from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from app.routers.errors import ERROR_RESPONSES

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskAuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    user_id: str | None = None
    tenant_id: str | None = None


class CreateTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    goal: str
    repo_path: str
    constraints: list[str] = Field(default_factory=list)
    auth_context: TaskAuthContext | None = None


class AgentTaskResponse(BaseModel):
    task_id: str
    agent_id: str
    goal: str
    repo_path: str
    status: str


class ApproveTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    approved_by: str
    comment: str | None = None


class ApprovalResponse(BaseModel):
    approval_id: str
    task_id: str
    status: str
    approved_by: str
    comment: str | None = None


@router.post(
    "",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
)
async def create_task(payload: CreateTaskPayload) -> AgentTaskResponse:
    return AgentTaskResponse(
        task_id="task_placeholder",
        agent_id=payload.agent_id,
        goal=payload.goal,
        repo_path=payload.repo_path,
        status="queued",
    )


@router.post(
    "/{task_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
)
async def approve_task_action(task_id: str, payload: ApproveTaskPayload) -> ApprovalResponse:
    return ApprovalResponse(
        approval_id=payload.approval_id,
        task_id=task_id,
        status="completed",
        approved_by=payload.approved_by,
        comment=payload.comment,
    )


@router.get("/{task_id}", responses=ERROR_RESPONSES)
async def get_task(task_id: str) -> dict[str, str]:
    return {"task_id": task_id, "message": "placeholder"}
