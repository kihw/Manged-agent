from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _error_payload(request: Request, status_code: int, code: str, message: str, details: list[ErrorDetail] | None):
    return ErrorResponse(
        code=code,
        message=message,
        status=status_code,
        trace_id=getattr(request.state, "trace_id", "trace_missing"),
        details=details,
        timestamp=datetime.now(UTC),
    ).model_dump(mode="json")


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(_, exc.status_code, exc.code, exc.message, exc.details),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(field=".".join(str(part) for part in err["loc"]), issue=err["msg"])
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "Request validation failed.",
            details,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(request, 500, "internal_error", str(exc), None),
    )


ERROR_RESPONSES = {
    code: {"model": ErrorResponse, "description": "Structured error response"}
    for code in (400, 401, 404, 409, 422, 500)
}
