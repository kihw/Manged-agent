from fastapi import APIRouter

from app.models import AuthContext, OAuthCallbackPayload, OAuthCallbackResponse
from app.routers.errors import ERROR_RESPONSES

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/oauth/callback",
    response_model=OAuthCallbackResponse,
    responses=ERROR_RESPONSES,
)
async def oauth_callback(payload: OAuthCallbackPayload) -> OAuthCallbackResponse:
    return OAuthCallbackResponse(
        status="authenticated",
        message=f"OAuth callback accepted for state={payload.state}",
    )


@router.get("/status", response_model=AuthContext, responses=ERROR_RESPONSES)
async def auth_status() -> AuthContext:
    return AuthContext(mode="auto", user_id=None, tenant_id=None)
