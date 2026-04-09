from fastapi import APIRouter, status

from app.models import AgentTask, ApprovalResponse, ApproveTaskPayload, CreateTaskRequest
from app.routers.errors import ERROR_RESPONSES

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=AgentTask,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
)
async def create_task(payload: CreateTaskRequest) -> AgentTask:
    return AgentTask(
        task_id="task_placeholder",
        trace_id="trace_placeholder",
        agent_id=payload.agent_id,
        goal=payload.goal,
        repo_path=payload.repo_path,
        constraints=payload.constraints,
        auth_context=payload.auth_context,
        status="queued",
        steps=[],
        tool_executions=[],
        approval_requests=[],
        artifacts=[],
        result_summary=None,
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
        status="approved",
        approved_by=payload.approved_by,
        comment=payload.comment,
    )


@router.get("/{task_id}", response_model=dict[str, str], responses=ERROR_RESPONSES)
async def get_task(task_id: str) -> dict[str, str]:
    return {"task_id": task_id, "message": "placeholder"}
