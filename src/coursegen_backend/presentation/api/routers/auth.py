"""Endpoints that open, renew and end sessions."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    RequestContext,
)
from coursegen_backend.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from coursegen_backend.application.use_cases.login import LoginUseCase
from coursegen_backend.application.use_cases.logout import LogoutUseCase
from coursegen_backend.application.use_cases.refresh_session import (
    RefreshSessionUseCase,
)
from coursegen_backend.presentation.api.dependencies import (
    get_current_principal,
    get_current_user_profile_use_case,
    get_login_use_case,
    get_logout_use_case,
    get_refresh_session_use_case,
    get_request_context,
)
from coursegen_backend.presentation.api.error_handlers import (
    error_response_doc,
)
from coursegen_backend.presentation.api.openapi_responses import (
    UNAUTHENTICATED_RESPONSE,
    VALIDATION_RESPONSE,
)
from coursegen_backend.presentation.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in with e-mail and password",
    description=(
        "Validates the institutional e-mail and password and opens a new "
        "session.\n\n"
        "The response carries:\n"
        "- an **access token** (JWT, valid for `ACCESS_TOKEN_TTL_MINUTES`, "
        "default 15 minutes) to send as `Authorization: Bearer <token>`;\n"
        "- a **refresh token**, used in `POST /auth/refresh` to renew the "
        "session without asking for the password again;\n"
        "- the **profile** of the user, with organizations and roles.\n\n"
        "For security, the error never tells whether the e-mail exists, "
        "the account is inactive or the password is wrong. After "
        "`LOGIN_MAX_FAILED_ATTEMPTS` failures (default 5) inside "
        "`LOGIN_THROTTLE_WINDOW_MINUTES` (default 15), the account is "
        "temporarily blocked and the API answers `429`, even for the "
        "correct password."
    ),
    response_description="Session credentials and the signed-in user.",
    responses={
        status.HTTP_401_UNAUTHORIZED: error_response_doc(
            "E-mail or password is incorrect, or the account cannot sign "
            "in with a password (`invalid_credentials`)."
        ),
        422: VALIDATION_RESPONSE,
        status.HTTP_429_TOO_MANY_REQUESTS: error_response_doc(
            "Too many failed attempts for this account "
            "(`too_many_login_attempts`). The `Retry-After` header tells "
            "how many seconds to wait."
        ),
    },
)
def login(
    payload: LoginRequest,
    use_case: Annotated[LoginUseCase, Depends(get_login_use_case)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> LoginResponse:
    """Sign the user in.

    Parameters
    ----------
    payload : LoginRequest
        Credentials of the user.
    use_case : LoginUseCase
        Sign-in use case.
    context : RequestContext
        Client information.

    Returns
    -------
    LoginResponse
        Session credentials and the user profile.
    """
    result = use_case.execute(
        email=payload.email,
        password=payload.password,
        keep_signed_in=payload.keep_signed_in,
        context=context,
    )
    tokens = TokenResponse.from_session_tokens(
        result.tokens,
        issued_at=datetime.now(UTC),
    )
    return LoginResponse(
        **tokens.model_dump(),
        user=UserResponse.from_profile(result.profile),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renew the session with a refresh token",
    description=(
        "Exchanges a refresh token for a new access token **and a new "
        "refresh token** (rotation). The informed refresh token stops "
        "working immediately, so the client must replace the stored one "
        "with the token returned here.\n\n"
        "Call this endpoint when an authenticated request answers `401`, "
        "or shortly before `access_token_expires_at`. The session keeps "
        "the lifetime chosen at sign-in (*keep me signed in* or not), "
        "counted again from each refresh."
    ),
    response_description="New credentials of the same session.",
    responses={
        status.HTTP_401_UNAUTHORIZED: error_response_doc(
            "The refresh token is unknown, was already rotated, expired, "
            "or its session was ended (`invalid_refresh_token`). The user "
            "must sign in again."
        ),
        422: VALIDATION_RESPONSE,
    },
)
def refresh(
    payload: RefreshRequest,
    use_case: Annotated[
        RefreshSessionUseCase, Depends(get_refresh_session_use_case)
    ],
) -> TokenResponse:
    """Renew the session of a refresh token.

    Parameters
    ----------
    payload : RefreshRequest
        Refresh token to exchange.
    use_case : RefreshSessionUseCase
        Session refresh use case.

    Returns
    -------
    TokenResponse
        New session credentials.
    """
    tokens = use_case.execute(payload.refresh_token)
    return TokenResponse.from_session_tokens(
        tokens,
        issued_at=datetime.now(UTC),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out of the current session",
    description=(
        "Ends the session of the access token. Both the access token and "
        "the refresh token of this session stop working immediately. "
        "Other sessions of the user (other devices) are not affected."
    ),
    response_description="Session ended; the response has no body.",
    responses={status.HTTP_401_UNAUTHORIZED: UNAUTHENTICATED_RESPONSE},
)
def logout(
    principal: Annotated[
        AuthenticatedPrincipal, Depends(get_current_principal)
    ],
    use_case: Annotated[LogoutUseCase, Depends(get_logout_use_case)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> Response:
    """End the current session.

    Parameters
    ----------
    principal : AuthenticatedPrincipal
        The authenticated user and session.
    use_case : LogoutUseCase
        Sign-out use case.
    context : RequestContext
        Client information.

    Returns
    -------
    Response
        Empty ``204`` response.
    """
    use_case.execute(principal, context)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user",
    description=(
        "Returns the profile of the owner of the access token, with the "
        "organizations they belong to and the roles held in each "
        "(`author`, `reviewer`, `curator`, `admin`). Useful to restore the "
        "interface after a page reload."
    ),
    response_description="Profile of the authenticated user.",
    responses={status.HTTP_401_UNAUTHORIZED: UNAUTHENTICATED_RESPONSE},
)
def read_current_user(
    principal: Annotated[
        AuthenticatedPrincipal, Depends(get_current_principal)
    ],
    use_case: Annotated[
        GetCurrentUserProfileUseCase,
        Depends(get_current_user_profile_use_case),
    ],
) -> UserResponse:
    """Return the authenticated user.

    Parameters
    ----------
    principal : AuthenticatedPrincipal
        The authenticated user and session.
    use_case : GetCurrentUserProfileUseCase
        Profile reading use case.

    Returns
    -------
    UserResponse
        Profile of the user.
    """
    return UserResponse.from_profile(use_case.execute(principal))
