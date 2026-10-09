"""Translation of errors into HTTP responses with a uniform body."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from coursegen_backend.domain.exceptions import (
    DomainError,
    IncorrectCurrentPasswordError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    PasswordReuseError,
    TooManyLoginAttemptsError,
    WeakPasswordError,
)
from coursegen_backend.presentation.api.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InvalidAccessTokenError: status.HTTP_401_UNAUTHORIZED,
    InvalidRefreshTokenError: status.HTTP_401_UNAUTHORIZED,
    TooManyLoginAttemptsError: status.HTTP_429_TOO_MANY_REQUESTS,
    InvalidPasswordResetTokenError: status.HTTP_400_BAD_REQUEST,
    WeakPasswordError: status.HTTP_400_BAD_REQUEST,
    PasswordReuseError: status.HTTP_400_BAD_REQUEST,
    IncorrectCurrentPasswordError: status.HTTP_400_BAD_REQUEST,
}


def error_response_doc(description: str) -> dict[str, Any]:
    """Describe an error response for the OpenAPI document.

    Parameters
    ----------
    description : str
        Explanation of when the status is returned, in Markdown.

    Returns
    -------
    dict[str, Any]
        Entry for the ``responses`` argument of a route.
    """
    return {"model": ErrorResponse, "description": description}


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Create a JSON response with the ``ErrorResponse`` body.

    Parameters
    ----------
    status_code : int
        HTTP status code.
    code : str
        Machine-readable error identifier.
    message : str
        Human-readable explanation.
    details : list[str] | None
        Additional explanations.
    headers : dict[str, str] | None
        Extra response headers.

    Returns
    -------
    JSONResponse
        The error response.
    """
    body = ErrorResponse(code=code, message=message, details=details)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )


async def handle_domain_error(
    _request: Request,
    error: DomainError,
) -> JSONResponse:
    """Translate a business error into its HTTP response.

    Parameters
    ----------
    _request : Request
        Request that failed (unused).
    error : DomainError
        Error raised by a use case.

    Returns
    -------
    JSONResponse
        Response with the mapped status code.
    """
    status_code = STATUS_BY_ERROR.get(
        type(error),
        status.HTTP_400_BAD_REQUEST,
    )
    headers = None
    details = None
    if isinstance(error, InvalidAccessTokenError):
        headers = {"WWW-Authenticate": "Bearer"}
    if isinstance(error, TooManyLoginAttemptsError):
        headers = {"Retry-After": str(error.retry_after_seconds)}
    if isinstance(error, WeakPasswordError):
        details = error.violations
    return build_error_response(
        status_code=status_code,
        code=error.code,
        message=error.message,
        details=details,
        headers=headers,
    )


async def handle_validation_error(
    _request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    """Translate request validation failures into ``ErrorResponse``.

    Parameters
    ----------
    _request : Request
        Request that failed (unused).
    error : RequestValidationError
        Validation error produced by FastAPI.

    Returns
    -------
    JSONResponse
        422 response listing each invalid field.
    """
    details = [
        f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
        for issue in error.errors()
    ]
    return build_error_response(
        status_code=422,
        code="validation_error",
        message="The request body or parameters are invalid.",
        details=details,
    )


async def handle_unexpected_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Log an unexpected failure and hide its internals from the client.

    Parameters
    ----------
    request : Request
        Request that failed.
    error : Exception
        Unhandled exception.

    Returns
    -------
    JSONResponse
        Generic 500 response.
    """
    logger.exception(
        "Unexpected error on %s %s",
        request.method,
        request.url.path,
        exc_info=error,
    )
    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="An unexpected error occurred. Try again later.",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach every error handler to the application.

    Parameters
    ----------
    app : FastAPI
        Application being configured.

    Returns
    -------
    None
    """
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
