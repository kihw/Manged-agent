from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_instance, get_services
from app.models import (
    BatchRunEventsRequest,
    CodexInstance,
    CompleteRunRequest,
    DashboardRunDetail,
    EventBatchAcceptedResponse,
    OperationStatusResponse,
    RunTask,
    StartRunRequest,
    StartRunResponse,
)
from app.routers.errors import ERROR_RESPONSES
from app.services.platform import PlatformService

router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=StartRunResponse, status_code=status.HTTP_201_CREATED, responses=ERROR_RESPONSES)
async def start_run(
    payload: StartRunRequest,
    instance: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> StartRunResponse:
    return services.start_run(payload, instance)


@router.get("/runs/{run_id}", response_model=DashboardRunDetail, responses=ERROR_RESPONSES)
async def get_run(
    run_id: str,
    instance: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> DashboardRunDetail:
    return services.get_run_detail(run_id, instance)


@router.post("/runs/{run_id}/events:batch", response_model=EventBatchAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses=ERROR_RESPONSES)
async def emit_run_events(
    run_id: str,
    payload: BatchRunEventsRequest,
    instance: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> EventBatchAcceptedResponse:
    return services.emit_events(run_id, payload, instance)


@router.post("/runs/{run_id}/complete", response_model=OperationStatusResponse, responses=ERROR_RESPONSES)
async def complete_run(
    run_id: str,
    payload: CompleteRunRequest,
    instance: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> OperationStatusResponse:
    return services.complete_run(run_id, payload, instance)


@router.get("/tasks/{task_id}", response_model=RunTask, responses=ERROR_RESPONSES)
async def get_task(
    task_id: str,
    _: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> RunTask:
    return services.get_task(task_id)
