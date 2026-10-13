"""Composition root: wires the use cases with their implementations.

Every FastAPI dependency below can be replaced through
``app.dependency_overrides``, which is how the tests run the API
without a database or the auth service.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from coursegen_backend.application.dto import AuthenticatedPrincipal
from coursegen_backend.application.ports.security import AccessTokenVerifier
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.application.use_cases.authenticate import (
    AuthenticateUseCase,
)
from coursegen_backend.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from coursegen_backend.domain.exceptions import InvalidAccessTokenError
from coursegen_backend.infrastructure.config import Settings, get_settings
from coursegen_backend.infrastructure.database.unit_of_work import (
    PostgresUnitOfWork,
)
from coursegen_backend.infrastructure.security.jwks_access_token_verifier import (
    JwksAccessTokenVerifier,
    build_jwks_key_resolver,
)

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description=(
        "Access token issued by the auth service "
        "(`POST /api/v1/auth/login` there). Paste only the token, without "
        "the `Bearer` prefix."
    ),
)


def get_app_settings() -> Settings:
    """Provide the application settings.

    Returns
    -------
    Settings
        Cached settings.
    """
    return get_settings()


def get_unit_of_work(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> UnitOfWork:
    """Provide a unit of work bound to the CourseGen database.

    Parameters
    ----------
    settings : Settings
        Application settings.

    Returns
    -------
    UnitOfWork
        PostgreSQL unit of work using ``COURSEGEN_DATABASE_URL``.
    """
    return PostgresUnitOfWork(settings.database_url.get_secret_value())


def get_access_token_verifier(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AccessTokenVerifier:
    """Provide the verifier of auth service tokens.

    Parameters
    ----------
    settings : Settings
        Application settings.

    Returns
    -------
    AccessTokenVerifier
        Verifier using the JWKS at ``AUTH_JWKS_URL``.
    """
    return JwksAccessTokenVerifier(
        signing_key_resolver=build_jwks_key_resolver(settings.auth_jwks_url),
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
    )


def get_authenticate_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    access_token_verifier: Annotated[
        AccessTokenVerifier, Depends(get_access_token_verifier)
    ],
) -> AuthenticateUseCase:
    """Provide the authentication use case.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.
    access_token_verifier : AccessTokenVerifier
        Verifies the access tokens.

    Returns
    -------
    AuthenticateUseCase
        Configured use case.
    """
    return AuthenticateUseCase(
        unit_of_work=unit_of_work,
        access_token_verifier=access_token_verifier,
    )


def get_current_user_profile_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> GetCurrentUserProfileUseCase:
    """Provide the use case that reads the authenticated user.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.

    Returns
    -------
    GetCurrentUserProfileUseCase
        Configured use case.
    """
    return GetCurrentUserProfileUseCase(unit_of_work=unit_of_work)


def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    authenticate_use_case: Annotated[
        AuthenticateUseCase, Depends(get_authenticate_use_case)
    ],
) -> AuthenticatedPrincipal:
    """Require a valid bearer access token and resolve its user.

    Parameters
    ----------
    credentials : HTTPAuthorizationCredentials | None
        Parsed ``Authorization`` header, when present.
    authenticate_use_case : AuthenticateUseCase
        Verifies the token and provisions the CourseGen profile.

    Returns
    -------
    AuthenticatedPrincipal
        The authenticated user.

    Raises
    ------
    InvalidAccessTokenError
        When the header is missing or the token is not valid.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidAccessTokenError()
    return authenticate_use_case.execute(credentials.credentials)
