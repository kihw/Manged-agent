from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.models import (
    CodexInstance,
    DashboardErrorDetail,
    DashboardErrorSummary,
    DashboardOverviewResponse,
    DashboardWorkflowDetail,
    DashboardWorkflowSummary,
    Orchestration,
    Run,
)
from app.dependencies import get_services
from app.services.platform import PlatformService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
page_router = APIRouter(tags=["pages"])


def _templates(request: Request):
    return request.app.state.templates


@router.get("/overview", response_model=DashboardOverviewResponse)
async def dashboard_overview(services: PlatformService = Depends(get_services)) -> DashboardOverviewResponse:
    return services.dashboard_overview()


@router.get("/orchestrations", response_model=list[Orchestration])
async def dashboard_orchestrations(services: PlatformService = Depends(get_services)):
    return services.list_dashboard_orchestrations()


@router.get("/instances", response_model=list[CodexInstance])
async def dashboard_instances(services: PlatformService = Depends(get_services)):
    return services.list_dashboard_instances()


@router.get("/runs", response_model=list[Run])
async def dashboard_runs(services: PlatformService = Depends(get_services)) -> list[Run]:
    return services.list_dashboard_runs()


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


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def dashboard_run_detail(run_id: str, request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    detail = services.get_run_detail(run_id)
    return _templates(request).TemplateResponse(
        request,
        "run_detail.html",
        {
            "detail": detail,
            "overview": services.dashboard_overview(),
        },
    )
@page_router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@page_router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "overview.html",
        {
            "overview": services.dashboard_overview(),
            "runs": services.list_dashboard_runs(),
            "instances": services.list_dashboard_instances(),
            "orchestrations": services.list_dashboard_orchestrations(),
        },
    )


@page_router.get("/dashboard/runs", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_runs_page(request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "runs.html",
        {
            "runs": services.list_dashboard_runs(),
        },
    )


@page_router.get("/dashboard/runs/{run_id}", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_run_detail_page(
    run_id: str,
    request: Request,
    services: PlatformService = Depends(get_services),
) -> HTMLResponse:
    detail = services.get_run_detail(run_id)
    return _templates(request).TemplateResponse(
        request,
        "run_detail.html",
        {
            "detail": detail,
            "overview": services.dashboard_overview(),
        },
    )


@page_router.get("/dashboard/workflows", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_workflows_page(
    request: Request,
    orchestration_id: str | None = None,
    terminal_status: str | None = None,
    limit: int = 50,
    services: PlatformService = Depends(get_services),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "workflows.html",
        {
            "workflows": services.list_dashboard_workflows(
                orchestration_id=orchestration_id,
                terminal_status=terminal_status,
                limit=limit,
            ),
            "filters": {
                "orchestration_id": orchestration_id or "",
                "terminal_status": terminal_status or "",
                "limit": limit,
            },
        },
    )


@page_router.get("/dashboard/workflows/{fingerprint_id}", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_workflow_detail_page(
    fingerprint_id: str,
    request: Request,
    limit: int = 10,
    services: PlatformService = Depends(get_services),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "workflow_detail.html",
        {
            "detail": services.get_dashboard_workflow_detail(fingerprint_id, limit=limit),
        },
    )


@page_router.get("/dashboard/instances", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_instances_page(request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "instances.html",
        {
            "instances": services.list_dashboard_instances(),
        },
    )


@page_router.get("/dashboard/errors", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_errors_page(
    request: Request,
    orchestration_id: str | None = None,
    instance_id: str | None = None,
    limit: int = 50,
    services: PlatformService = Depends(get_services),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "errors.html",
        {
            "errors": services.list_dashboard_errors(
                orchestration_id=orchestration_id,
                instance_id=instance_id,
                limit=limit,
            ),
            "filters": {
                "orchestration_id": orchestration_id or "",
                "instance_id": instance_id or "",
                "limit": limit,
            },
        },
    )


@page_router.get("/dashboard/errors/{category}", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_error_detail_page(
    category: str,
    request: Request,
    orchestration_id: str | None = None,
    instance_id: str | None = None,
    limit: int = 10,
    services: PlatformService = Depends(get_services),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "error_detail.html",
        {
            "detail": services.get_dashboard_error_detail(
                category,
                orchestration_id=orchestration_id,
                instance_id=instance_id,
                limit=limit,
            ),
        },
    )


@page_router.get("/dashboard/orchestrations", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_orchestrations_page(request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "orchestrations.html",
        {
            "orchestrations": services.list_dashboard_orchestrations(),
        },
    )
