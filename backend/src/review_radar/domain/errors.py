"""Typed errors with stable codes.

The API layer maps each code to an HTTP status and a single error envelope, so
clients can branch on `code` instead of parsing messages.
"""

from collections.abc import Mapping
from enum import StrEnum


class ErrorCode(StrEnum):
    NOT_FOUND = "not_found"
    VALIDATION = "validation_error"
    INVALID_TRANSITION = "invalid_transition"
    REPLY_INVALID = "reply_invalid"
    SOURCE_NOT_CONFIGURED = "source_not_configured"
    STORE_API = "store_api_error"
    LLM = "llm_error"


class AppError(Exception):
    code: ErrorCode = ErrorCode.VALIDATION

    def __init__(self, message: str, *, details: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = dict(details or {})


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND


class InvalidTransitionError(AppError):
    code = ErrorCode.INVALID_TRANSITION


class ReplyInvalidError(AppError):
    code = ErrorCode.REPLY_INVALID


class SourceNotConfiguredError(AppError):
    code = ErrorCode.SOURCE_NOT_CONFIGURED


class StoreApiError(AppError):
    code = ErrorCode.STORE_API


class LlmError(AppError):
    code = ErrorCode.LLM
