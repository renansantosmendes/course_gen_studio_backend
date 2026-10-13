"""Endpoint that returns the authenticated user's CourseGen profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from coursegen_backend.application.dto import AuthenticatedPrincipal
from coursegen_backend.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from coursegen_backend.presentation.api.dependencies import (
    get_current_principal,
    get_current_user_profile_use_case,
)
from coursegen_backend.presentation.api.openapi_responses import (
    ACCOUNT_DISABLED_RESPONSE,
    ACCOUNT_LINK_CONFLICT_RESPONSE,
    AUTH_SERVICE_UNAVAILABLE_RESPONSE,
    UNAUTHENTICATED_RESPONSE,
)
from coursegen_backend.presentation.api.schemas.profile import (
    UserProfileResponse,
)

router = APIRouter(tags=["Profile"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get the authenticated user's CourseGen profile",
    description=(
        "Returns the CourseGen Studio profile of the owner of the access "
        "token, with the organizations they belong to and the roles held "
        "in each (`author`, `reviewer`, `curator`, `admin`).\n\n"
        "Sign-in happens in the **auth service**: send the access token it "
        "issued as `Authorization: Bearer <access_token>`. On the first "
        "request of an account, its CourseGen profile is created with the "
        "token's identifier, e-mail and name; later requests keep e-mail "
        "and name in sync."
    ),
    response_description="Profile of the authenticated user.",
    responses={
        status.HTTP_401_UNAUTHORIZED: UNAUTHENTICATED_RESPONSE,
        status.HTTP_403_FORBIDDEN: ACCOUNT_DISABLED_RESPONSE,
        status.HTTP_409_CONFLICT: ACCOUNT_LINK_CONFLICT_RESPONSE,
        status.HTTP_503_SERVICE_UNAVAILABLE: AUTH_SERVICE_UNAVAILABLE_RESPONSE,
    },
)
def read_current_user(
    principal: Annotated[
        AuthenticatedPrincipal, Depends(get_current_principal)
    ],
    use_case: Annotated[
        GetCurrentUserProfileUseCase,
        Depends(get_current_user_profile_use_case),
    ],
) -> UserProfileResponse:
    """Return the authenticated user's profile.

    Parameters
    ----------
    principal : AuthenticatedPrincipal
        The authenticated user.
    use_case : GetCurrentUserProfileUseCase
        Profile reading use case.

    Returns
    -------
    UserProfileResponse
        Profile of the user with their organizations.
    """
    return UserProfileResponse.from_profile(use_case.execute(principal))
