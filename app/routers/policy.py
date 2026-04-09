from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.dependencies import get_current_instance, get_services
from app.models import CodexInstance, PolicyDecision, PolicyDecisionResolutionRequest, PreauthorizeActionRequest
from app.routers.errors import ERROR_RESPONSES
from app.services.platform import PlatformService

router = APIRouter(prefix="/policy", tags=["policy"])
decision_router = APIRouter(prefix="/policy-decisions", tags=["policy"])


@router.post("/preauthorize", response_model=PolicyDecision, responses=ERROR_RESPONSES)
async def preauthorize_action(
    payload: PreauthorizeActionRequest,
    instance: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> PolicyDecision:
    return services.preauthorize_action(payload, instance)


@decision_router.get("/{decision_id}", response_model=PolicyDecision, responses=ERROR_RESPONSES)
async def get_policy_decision(
    decision_id: str,
    _: CodexInstance = Depends(get_current_instance),
    services: PlatformService = Depends(get_services),
) -> PolicyDecision:
    return services.get_policy_decision(decision_id)


@decision_router.post("/{decision_id}/resolve", response_model=PolicyDecision, responses=ERROR_RESPONSES)
async def resolve_policy_decision(
    decision_id: str,
    request: Request,
    services: PlatformService = Depends(get_services),
) -> PolicyDecision | RedirectResponse:
    if request.headers.get("content-type", "").startswith("application/json"):
        payload = PolicyDecisionResolutionRequest.model_validate(await request.json())
        return services.resolve_policy_decision(decision_id, payload)

    raw_body = (await request.body()).decode("utf-8")
    form = {key: values[-1] for key, values in parse_qs(raw_body, keep_blank_values=True).items()}
    payload = PolicyDecisionResolutionRequest(
        resolution=str(form.get("resolution", "denied")),
        resolved_by=str(form.get("resolved_by", "dashboard")),
        comment=str(form.get("comment")) if form.get("comment") else None,
    )
    decision = services.resolve_policy_decision(decision_id, payload)
    return RedirectResponse(url=f"/dashboard/runs/{decision.run_id}", status_code=303)
