from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import yaml

import app.routers.dashboard as dashboard
import app.routers.instances as instances
import app.routers.orchestrations as orchestrations
import app.routers.policy as policy
import app.routers.runs as runs
from app.routers.errors import ApiError, _error_payload, api_error_handler, unhandled_exception_handler, validation_error_handler
from app.runtime import RuntimePaths, resolve_runtime_paths
from app.services.platform import PlatformService
from app.services.settings import AppSettings, new_public_id, resolve_settings


def create_app(
    *,
    settings: AppSettings | None = None,
    runtime_paths: RuntimePaths | None = None,
) -> FastAPI:
    paths = runtime_paths or resolve_runtime_paths()
    resolved_settings = settings or resolve_settings(runtime_paths=paths)
    if resolved_settings.enforce_admin_auth and not resolved_settings.admin_secret:
        raise RuntimeError("MANAGED_AGENT_ADMIN_SECRET is required when admin auth is enforced.")
    app = FastAPI(title="Managed Agent V1 Platform", version="1.0.0")
    app.state.services = PlatformService(resolved_settings)
    app.state.runtime_paths = paths
    app.state.templates = Jinja2Templates(directory=str(paths.templates_dir))
    openapi_path = paths.openapi_path

    @app.middleware("http")
    async def attach_trace_id(request: Request, call_next):
        request.state.trace_id = new_public_id("trace")
        should_set_cookie = False
        if resolved_settings.enforce_admin_auth and request.url.path != "/healthz":
            expected_secret = resolved_settings.admin_secret
            provided_secret = (
                request.headers.get("X-Admin-Secret")
                or request.cookies.get("managed_agent_admin")
                or request.query_params.get("admin_secret")
            )
            if expected_secret is None or provided_secret != expected_secret:
                return JSONResponse(
                    status_code=401,
                    content=_error_payload(request, 401, "admin_auth_required", "Admin authentication is required.", None),
                )
            should_set_cookie = request.query_params.get("admin_secret") == expected_secret
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        if should_set_cookie:
            response.set_cookie("managed_agent_admin", resolved_settings.admin_secret, httponly=True, samesite="lax")
        return response

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/healthz", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
    async def published_openapi_yaml() -> PlainTextResponse:
        return PlainTextResponse(openapi_path.read_text(encoding="utf-8"), media_type="application/yaml")

    app.include_router(dashboard.page_router)
    app.include_router(instances.router, prefix="/v1")
    app.include_router(orchestrations.router, prefix="/v1")
    app.include_router(runs.router, prefix="/v1")
    app.include_router(policy.router, prefix="/v1")
    app.include_router(policy.decision_router, prefix="/v1")
    app.include_router(dashboard.router, prefix="/v1")

    cached_openapi: dict[str, object] | None = None

    def load_published_openapi() -> dict[str, object]:
        nonlocal cached_openapi
        if cached_openapi is None and openapi_path.exists():
            cached_openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
        if cached_openapi is not None:
            return cached_openapi
        return get_openapi(title=app.title, version=app.version, routes=app.routes)

    app.openapi = load_published_openapi  # type: ignore[assignment]
    return app


app = create_app()
