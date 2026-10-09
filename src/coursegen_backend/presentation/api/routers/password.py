"""Endpoints that recover and change passwords."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    RequestContext,
)
from coursegen_backend.application.use_cases.change_password import (
    ChangePasswordUseCase,
)
from coursegen_backend.application.use_cases.request_password_reset import (
    RequestPasswordResetUseCase,
)
from coursegen_backend.application.use_cases.reset_password import (
    ResetPasswordUseCase,
)
from coursegen_backend.presentation.api.dependencies import (
    get_change_password_use_case,
    get_current_principal,
    get_request_context,
    get_request_password_reset_use_case,
    get_reset_password_use_case,
)
from coursegen_backend.presentation.api.error_handlers import (
    error_response_doc,
)
from coursegen_backend.presentation.api.openapi_responses import (
    UNAUTHENTICATED_RESPONSE,
    VALIDATION_RESPONSE,
)
from coursegen_backend.presentation.api.schemas.common import MessageResponse
from coursegen_backend.presentation.api.schemas.password import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

FORGOT_PASSWORD_MESSAGE = (
    "If an account is associated with this e-mail, recovery instructions "
    "have been sent."
)
WEAK_PASSWORD_DESCRIPTION = (
    "`weak_password`: the new password breaks the password policy "
    "(`details` lists each broken rule); `password_reuse`: the new "
    "password equals the current one."
)

router = APIRouter(prefix="/auth/password", tags=["Password management"])


@router.post(
    "/forgot",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password recovery e-mail",
    description=(
        "Starts the *Forgot my password* flow. When the e-mail belongs to "
        "an active account that signs in with a password, a single-use "
        "link valid for `PASSWORD_RESET_TTL_MINUTES` (default 30 minutes) "
        "is e-mailed to it:\n\n"
        "`<PASSWORD_RESET_URL>#reset_token=<token>`\n\n"
        "The front end must read `reset_token` from the URL fragment and "
        "send it to `POST /auth/password/reset`.\n\n"
        "**The response is always the same `202`**, whether or not the "
        "account exists, so the endpoint cannot be used to discover "
        "registered e-mails. Requesting a new link does not invalidate "
        "the previous ones; all of them are invalidated once the password "
        "is reset."
    ),
    response_description="Neutral confirmation that the request was taken.",
    responses={422: VALIDATION_RESPONSE},
)
def forgot_password(
    payload: ForgotPasswordRequest,
    use_case: Annotated[
        RequestPasswordResetUseCase,
        Depends(get_request_password_reset_use_case),
    ],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> MessageResponse:
    """Send recovery instructions when the account exists.

    Parameters
    ----------
    payload : ForgotPasswordRequest
        E-mail of the account.
    use_case : RequestPasswordResetUseCase
        Recovery request use case.
    context : RequestContext
        Client information.

    Returns
    -------
    MessageResponse
        Neutral confirmation.
    """
    use_case.execute(payload.email, context)
    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post(
    "/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Define a new password with a recovery token",
    description=(
        "Completes the recovery flow with the token from the e-mail link. "
        "On success:\n"
        "- the password is replaced;\n"
        "- the token and every other pending recovery token of the user "
        "are invalidated;\n"
        "- **every session of the user is ended**, on all devices.\n\n"
        "The user must then sign in with the new password."
    ),
    response_description="Password replaced; the response has no body.",
    responses={
        status.HTTP_400_BAD_REQUEST: error_response_doc(
            "`invalid_password_reset_token`: the token is unknown, "
            "expired or already used. "
            + WEAK_PASSWORD_DESCRIPTION
        ),
        422: VALIDATION_RESPONSE,
    },
)
def reset_password(
    payload: ResetPasswordRequest,
    use_case: Annotated[
        ResetPasswordUseCase, Depends(get_reset_password_use_case)
    ],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> Response:
    """Replace the password using a recovery token.

    Parameters
    ----------
    payload : ResetPasswordRequest
        Recovery token and new password.
    use_case : ResetPasswordUseCase
        Password reset use case.
    context : RequestContext
        Client information.

    Returns
    -------
    Response
        Empty ``204`` response.
    """
    use_case.execute(
        reset_token=payload.reset_token,
        new_password=payload.new_password,
        context=context,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/change",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the password of the authenticated user",
    description=(
        "Replaces the password after confirming the current one. The "
        "session that made the request **stays open**; every other "
        "session of the user (other devices) is ended, and pending "
        "recovery links are invalidated."
    ),
    response_description="Password replaced; the response has no body.",
    responses={
        status.HTTP_400_BAD_REQUEST: error_response_doc(
            "`incorrect_current_password`: the current password is "
            "wrong. " + WEAK_PASSWORD_DESCRIPTION
        ),
        status.HTTP_401_UNAUTHORIZED: UNAUTHENTICATED_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
def change_password(
    payload: ChangePasswordRequest,
    principal: Annotated[
        AuthenticatedPrincipal, Depends(get_current_principal)
    ],
    use_case: Annotated[
        ChangePasswordUseCase, Depends(get_change_password_use_case)
    ],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> Response:
    """Change the password of the authenticated user.

    Parameters
    ----------
    payload : ChangePasswordRequest
        Current and new password.
    principal : AuthenticatedPrincipal
        The authenticated user and session.
    use_case : ChangePasswordUseCase
        Password change use case.
    context : RequestContext
        Client information.

    Returns
    -------
    Response
        Empty ``204`` response.
    """
    use_case.execute(
        principal=principal,
        current_password=payload.current_password,
        new_password=payload.new_password,
        context=context,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
