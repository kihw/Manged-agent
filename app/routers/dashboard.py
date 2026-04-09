from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.models import CodexInstance, DashboardOverviewResponse, Orchestration, Run
from app.dependencies import get_services
from app.services.platform import PlatformService

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
page_router = APIRouter(tags=["pages"])


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


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def dashboard_run_detail(run_id: str, request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    detail = services.get_run_detail(run_id)
    return templates.TemplateResponse(
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
    return templates.TemplateResponse(
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
    return templates.TemplateResponse(
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
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "detail": detail,
            "overview": services.dashboard_overview(),
        },
    )


@page_router.get("/dashboard/instances", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_instances_page(request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "instances.html",
        {
            "instances": services.list_dashboard_instances(),
        },
    )


@page_router.get("/dashboard/orchestrations", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_orchestrations_page(request: Request, services: PlatformService = Depends(get_services)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "orchestrations.html",
        {
            "orchestrations": services.list_dashboard_orchestrations(),
        },
    )
