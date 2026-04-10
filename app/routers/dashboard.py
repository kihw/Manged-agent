from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.models import (
    CodexInstance,
    DashboardCommandCenterResponse,
    DashboardErrorDetail,
    DashboardErrorSummary,
    DashboardLaunchRunRequest,
    DashboardOverviewResponse,
    DashboardRelaunchRunRequest,
    DashboardRunDetail,
    DashboardWorkflowDetail,
    DashboardWorkflowSummary,
    Orchestration,
    Run,
    StartRunResponse,
)
from app.dependencies import get_services
from app.services.platform import PlatformService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
page_router = APIRouter(tags=["pages"])


def _local_instance(request: Request) -> CodexInstance:
    instance = request.app.state.desktop_instance_manager.ensure_local_instance()
    request.app.state.local_desktop_instance = instance
    return instance


@router.get("/overview", response_model=DashboardOverviewResponse)
async def dashboard_overview(services: PlatformService = Depends(get_services)) -> DashboardOverviewResponse:
    return services.dashboard_overview()


@router.get("/orchestrations", response_model=list[Orchestration])
async def dashboard_orchestrations(services: PlatformService = Depends(get_services)):
    return services.list_dashboard_orchestrations()


@router.get("/command-center", response_model=DashboardCommandCenterResponse)
async def dashboard_command_center(
    request: Request,
    services: PlatformService = Depends(get_services),
) -> DashboardCommandCenterResponse:
    return services.dashboard_command_center(
        local_instance=_local_instance(request),
        admin_auth_required=services.settings.enforce_admin_auth,
    )


@router.get("/instances", response_model=list[CodexInstance])
async def dashboard_instances(services: PlatformService = Depends(get_services)):
    return services.list_dashboard_instances()


@router.get("/runs", response_model=list[Run])
async def dashboard_runs(services: PlatformService = Depends(get_services)) -> list[Run]:
    return services.list_dashboard_runs()


@router.post("/runs/launch", response_model=StartRunResponse, status_code=201)
async def dashboard_launch_run(
    payload: DashboardLaunchRunRequest,
    request: Request,
    services: PlatformService = Depends(get_services),
) -> StartRunResponse:
    return services.launch_run_from_dashboard(payload, _local_instance(request))


@router.post("/runs/{run_id}/relaunch", response_model=StartRunResponse, status_code=201)
async def dashboard_relaunch_run(
    run_id: str,
    payload: DashboardRelaunchRunRequest,
    request: Request,
    services: PlatformService = Depends(get_services),
) -> StartRunResponse:
    return services.relaunch_run_from_dashboard(run_id, payload, _local_instance(request))


@router.get("/runs/{run_id}", response_model=DashboardRunDetail)
async def dashboard_run_detail(run_id: str, services: PlatformService = Depends(get_services)) -> DashboardRunDetail:
    return services.get_run_detail(run_id)


@router.get("/workflows", response_model=list[DashboardWorkflowSummary])
async def dashboard_workflows(
    orchestration_id: str | None = None,
    terminal_status: str | None = None,
    limit: int = 50,
    services: PlatformService = Depends(get_services),
) -> list[DashboardWorkflowSummary]:
    return services.list_dashboard_workflows(
        orchestration_id=orchestration_id,
        terminal_status=terminal_status,
        limit=limit,
    )


@router.get("/workflows/{fingerprint_id}", response_model=DashboardWorkflowDetail)
async def dashboard_workflow_detail(
    fingerprint_id: str,
    limit: int = 10,
    services: PlatformService = Depends(get_services),
) -> DashboardWorkflowDetail:
    return services.get_dashboard_workflow_detail(fingerprint_id, limit=limit)


@router.get("/errors", response_model=list[DashboardErrorSummary])
async def dashboard_errors(
    orchestration_id: str | None = None,
    instance_id: str | None = None,
    limit: int = 50,
    services: PlatformService = Depends(get_services),
) -> list[DashboardErrorSummary]:
    return services.list_dashboard_errors(
        orchestration_id=orchestration_id,
        instance_id=instance_id,
        limit=limit,
    )


@router.get("/errors/{category}", response_model=DashboardErrorDetail)
async def dashboard_error_detail(
    category: str,
    orchestration_id: str | None = None,
    instance_id: str | None = None,
    limit: int = 10,
    services: PlatformService = Depends(get_services),
) -> DashboardErrorDetail:
    return services.get_dashboard_error_detail(
        category,
        orchestration_id=orchestration_id,
        instance_id=instance_id,
        limit=limit,
    )




def _shell_path(request: Request) -> Path:
    return request.app.state.runtime_paths.frontend_dist_dir / "index.html"


def _serve_shell(request: Request) -> FileResponse:
    shell_path = _shell_path(request)
    if not shell_path.exists():
        raise HTTPException(status_code=503, detail="Dashboard frontend is not built.")
    return FileResponse(shell_path, media_type="text/html")
@page_router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@page_router.get("/dashboard", include_in_schema=False)
async def dashboard_page(request: Request) -> FileResponse:
    return _serve_shell(request)


@page_router.get("/dashboard/{path:path}", include_in_schema=False)
async def dashboard_spa_page(path: str, request: Request) -> FileResponse:
    return _serve_shell(request)
