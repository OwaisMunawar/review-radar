"""One error envelope for every failure the API can return."""

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from review_radar.domain.errors import AppError, ErrorCode

log = structlog.get_logger(__name__)

STATUS: dict[ErrorCode, HTTPStatus] = {
    ErrorCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.VALIDATION: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.INVALID_TRANSITION: HTTPStatus.CONFLICT,
    ErrorCode.REPLY_INVALID: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.SOURCE_NOT_CONFIGURED: HTTPStatus.SERVICE_UNAVAILABLE,
    ErrorCode.STORE_API: HTTPStatus.BAD_GATEWAY,
    ErrorCode.LLM: HTTPStatus.BAD_GATEWAY,
}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


def _respond(
    status: HTTPStatus, code: str, message: str, details: dict[str, object]
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered for AppError only
    return _respond(STATUS[exc.code], exc.code.value, exc.message, exc.details)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    errors = [
        {"loc": [str(p) for p in e.get("loc", ())], "msg": str(e.get("msg", ""))}
        for e in exc.errors()
    ]
    return _respond(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        ErrorCode.VALIDATION.value,
        "request validation failed",
        {"errors": errors},
    )


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("api.unhandled", path=request.url.path)
    return _respond(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "unexpected error", {})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected)


ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Invalid state transition"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
