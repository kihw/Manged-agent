from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.routers.errors import ERROR_RESPONSES

router = APIRouter(prefix="/auth", tags=["auth"])


class OAuthCallbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    state: str
    code_verifier: str


class OAuthCallbackResponse(BaseModel):
    status: str
    message: str


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


@router.get("/status", responses=ERROR_RESPONSES)
async def auth_status() -> dict[str, str]:
    return {"status": "placeholder"}
