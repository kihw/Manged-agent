from __future__ import annotations

from fastapi import Depends, Header, Request

from app.models import CodexInstance
from app.services.platform import PlatformService


def get_services(request: Request) -> PlatformService:
    return request.app.state.services


def get_current_instance(
    x_instance_token: str | None = Header(default=None, alias="X-Instance-Token"),
    services: PlatformService = Depends(get_services),
) -> CodexInstance:
    return services.authenticate_instance(x_instance_token)
