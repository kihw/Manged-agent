from fastapi import APIRouter, Depends, status

from app.dependencies import get_services
from app.models import RegisterInstanceRequest, RegisterInstanceResponse
from app.routers.errors import ERROR_RESPONSES
from app.services.platform import PlatformService

router = APIRouter(prefix="/instances", tags=["instances"])


@router.post("/register", response_model=RegisterInstanceResponse, status_code=status.HTTP_201_CREATED, responses=ERROR_RESPONSES)
async def register_instance(
    payload: RegisterInstanceRequest,
    services: PlatformService = Depends(get_services),
) -> RegisterInstanceResponse:
    return services.register_instance(payload)
