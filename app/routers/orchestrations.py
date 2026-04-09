from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_instance, get_services
from app.models import CodexInstance, Orchestration, SyncOrchestrationsResponse
from app.routers.errors import ERROR_RESPONSES
from app.services.platform import PlatformService

router = APIRouter(prefix="/orchestrations", tags=["orchestrations"])


@router.post("", response_model=Orchestration, status_code=status.HTTP_201_CREATED, responses=ERROR_RESPONSES)
async def publish_orchestration(
    payload: Orchestration,
    services: PlatformService = Depends(get_services),
) -> Orchestration:
    return services.publish_orchestration(payload)


@router.get("/sync", response_model=SyncOrchestrationsResponse, responses=ERROR_RESPONSES)
async def sync_orchestrations(
    instance: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> SyncOrchestrationsResponse:
    return services.sync_orchestrations(instance)


@router.get("/{orchestration_id}", response_model=Orchestration, responses=ERROR_RESPONSES)
async def get_orchestration(
    orchestration_id: str,
    services: PlatformService = Depends(get_services),
) -> Orchestration:
    return services.get_orchestration(orchestration_id)
