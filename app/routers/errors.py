from __future__ import annotations

from datetime import datetime, timezone

from fastapi import status
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str
    issue: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    status: int = Field(ge=100, le=599)
    trace_id: str
    details: list[ErrorDetail] | None = None
    timestamp: datetime


ERROR_STATUS_CODES: tuple[int, ...] = (
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_409_CONFLICT,
    status.HTTP_422_UNPROCESSABLE_ENTITY,
    status.HTTP_429_TOO_MANY_REQUESTS,
    status.HTTP_500_INTERNAL_SERVER_ERROR,
)


def make_error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    trace_id: str = "trace_placeholder",
    details: list[ErrorDetail] | None = None,
) -> ErrorResponse:
    return ErrorResponse(
        code=code,
        message=message,
        status=status_code,
        trace_id=trace_id,
        details=details,
        timestamp=datetime.now(timezone.utc),
    )


ERROR_RESPONSES = {
    error_status: {
        "model": ErrorResponse,
        "description": "Structured error response",
    }
    for error_status in ERROR_STATUS_CODES
}
