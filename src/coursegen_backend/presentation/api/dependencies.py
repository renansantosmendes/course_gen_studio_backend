"""Composition root: wires the use cases with their implementations.

Every FastAPI dependency below can be replaced through
``app.dependency_overrides``, which is how the tests run the API
without a database.
"""

from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    RequestContext,
)
from coursegen_backend.application.policies import (
    LoginThrottlePolicy,
    PasswordResetPolicy,
    SessionPolicy,
)
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.email import EmailSender
from coursegen_backend.application.ports.security import (
    AccessTokenService,
    OpaqueTokenGenerator,
    PasswordHasher,
)
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.application.use_cases.authenticate import (
    AuthenticateUseCase,
)
from coursegen_backend.application.use_cases.change_password import (
    ChangePasswordUseCase,
)
from coursegen_backend.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from coursegen_backend.application.use_cases.login import LoginUseCase
from coursegen_backend.application.use_cases.logout import LogoutUseCase
from coursegen_backend.application.use_cases.refresh_session import (
    RefreshSessionUseCase,
)
from coursegen_backend.application.use_cases.request_password_reset import (
    RequestPasswordResetUseCase,
)
from coursegen_backend.application.use_cases.reset_password import (
    ResetPasswordUseCase,
)
from coursegen_backend.domain.exceptions import InvalidAccessTokenError
from coursegen_backend.domain.password_policy import PasswordPolicy
from coursegen_backend.infrastructure.clock import SystemClock
from coursegen_backend.infrastructure.config import Settings, get_settings
from coursegen_backend.infrastructure.database.unit_of_work import (
    PostgresUnitOfWork,
)
from coursegen_backend.infrastructure.email.factory import (
    build_email_sender,
)
from coursegen_backend.infrastructure.security.argon2_password_hasher import (
    Argon2PasswordHasher,
)
from coursegen_backend.infrastructure.security.jwt_access_token_service import (
    JwtAccessTokenService,
)
from coursegen_backend.infrastructure.security.opaque_token_generator import (
    SecretsOpaqueTokenGenerator,
)
from coursegen_backend.presentation.api.request_context import (
    build_request_context,
)

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description=(
        "Access token returned by `POST /api/v1/auth/login` or "
        "`POST /api/v1/auth/refresh`. Paste only the token, without the "
        "`Bearer` prefix."
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


@lru_cache
def get_password_hasher() -> PasswordHasher:
    """Provide the password hasher, created once per process.

    Returns
    -------
    PasswordHasher
        Argon2id hasher.
    """
    return Argon2PasswordHasher()


def get_token_generator() -> OpaqueTokenGenerator:
    """Provide the generator of refresh and reset tokens.

    Returns
    -------
    OpaqueTokenGenerator
        Generator based on the ``secrets`` module.
    """
    return SecretsOpaqueTokenGenerator()


def get_clock() -> Clock:
    """Provide the source of the current time.

    Returns
    -------
    Clock
        System clock.
    """
    return SystemClock()


def get_password_policy() -> PasswordPolicy:
    """Provide the password strength rules.

    Returns
    -------
    PasswordPolicy
        Default password policy.
    """
    return PasswordPolicy()


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


def get_access_token_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AccessTokenService:
    """Provide the JWT access token service.

    Parameters
    ----------
    settings : Settings
        Application settings.

    Returns
    -------
    AccessTokenService
        Service signing tokens with ``COURSEGEN_JWT_SECRET_KEY``.
    """
    return JwtAccessTokenService(
        secret_key=settings.jwt_secret_key.get_secret_value(),
        time_to_live=timedelta(minutes=settings.access_token_ttl_minutes),
        issuer=settings.jwt_issuer,
    )


def get_email_sender(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> EmailSender:
    """Provide the configured e-mail sender.

    Parameters
    ----------
    settings : Settings
        Application settings.

    Returns
    -------
    EmailSender
        SMTP or logging sender, according to ``EMAIL_BACKEND``.
    """
    return build_email_sender(settings)


def get_session_token_issuer(
    settings: Annotated[Settings, Depends(get_app_settings)],
    access_token_service: Annotated[
        AccessTokenService, Depends(get_access_token_service)
    ],
    token_generator: Annotated[
        OpaqueTokenGenerator, Depends(get_token_generator)
    ],
) -> SessionTokenIssuer:
    """Provide the service that issues session credentials.

    Parameters
    ----------
    settings : Settings
        Application settings.
    access_token_service : AccessTokenService
        Issues access tokens.
    token_generator : OpaqueTokenGenerator
        Creates refresh tokens.

    Returns
    -------
    SessionTokenIssuer
        Configured issuer.
    """
    return SessionTokenIssuer(
        access_token_service=access_token_service,
        token_generator=token_generator,
        session_policy=SessionPolicy(
            refresh_token_ttl=timedelta(
                hours=settings.refresh_token_ttl_hours
            ),
            keep_signed_in_refresh_token_ttl=timedelta(
                days=settings.keep_signed_in_ttl_days
            ),
        ),
    )


def get_login_use_case(
    settings: Annotated[Settings, Depends(get_app_settings)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    session_token_issuer: Annotated[
        SessionTokenIssuer, Depends(get_session_token_issuer)
    ],
    clock: Annotated[Clock, Depends(get_clock)],
) -> LoginUseCase:
    """Provide the sign-in use case.

    Parameters
    ----------
    settings : Settings
        Application settings.
    unit_of_work : UnitOfWork
        Transaction boundary.
    password_hasher : PasswordHasher
        Password hasher.
    session_token_issuer : SessionTokenIssuer
        Issues session credentials.
    clock : Clock
        Source of the current time.

    Returns
    -------
    LoginUseCase
        Configured use case.
    """
    return LoginUseCase(
        unit_of_work=unit_of_work,
        password_hasher=password_hasher,
        session_token_issuer=session_token_issuer,
        throttle_policy=LoginThrottlePolicy(
            max_failed_attempts=settings.login_max_failed_attempts,
            window=timedelta(minutes=settings.login_throttle_window_minutes),
        ),
        clock=clock,
    )


def get_refresh_session_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    token_generator: Annotated[
        OpaqueTokenGenerator, Depends(get_token_generator)
    ],
    session_token_issuer: Annotated[
        SessionTokenIssuer, Depends(get_session_token_issuer)
    ],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RefreshSessionUseCase:
    """Provide the session refresh use case.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.
    token_generator : OpaqueTokenGenerator
        Hashes refresh tokens.
    session_token_issuer : SessionTokenIssuer
        Issues session credentials.
    clock : Clock
        Source of the current time.

    Returns
    -------
    RefreshSessionUseCase
        Configured use case.
    """
    return RefreshSessionUseCase(
        unit_of_work=unit_of_work,
        token_generator=token_generator,
        session_token_issuer=session_token_issuer,
        clock=clock,
    )


def get_authenticate_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    access_token_service: Annotated[
        AccessTokenService, Depends(get_access_token_service)
    ],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AuthenticateUseCase:
    """Provide the access token validation use case.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.
    access_token_service : AccessTokenService
        Decodes access tokens.
    clock : Clock
        Source of the current time.

    Returns
    -------
    AuthenticateUseCase
        Configured use case.
    """
    return AuthenticateUseCase(
        unit_of_work=unit_of_work,
        access_token_service=access_token_service,
        clock=clock,
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


def get_logout_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> LogoutUseCase:
    """Provide the sign-out use case.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.
    clock : Clock
        Source of the current time.

    Returns
    -------
    LogoutUseCase
        Configured use case.
    """
    return LogoutUseCase(unit_of_work=unit_of_work, clock=clock)


def get_request_password_reset_use_case(
    settings: Annotated[Settings, Depends(get_app_settings)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    token_generator: Annotated[
        OpaqueTokenGenerator, Depends(get_token_generator)
    ],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RequestPasswordResetUseCase:
    """Provide the password recovery request use case.

    Parameters
    ----------
    settings : Settings
        Application settings.
    unit_of_work : UnitOfWork
        Transaction boundary.
    token_generator : OpaqueTokenGenerator
        Creates reset tokens.
    email_sender : EmailSender
        Delivers the recovery e-mail.
    clock : Clock
        Source of the current time.

    Returns
    -------
    RequestPasswordResetUseCase
        Configured use case.
    """
    return RequestPasswordResetUseCase(
        unit_of_work=unit_of_work,
        token_generator=token_generator,
        email_sender=email_sender,
        reset_policy=PasswordResetPolicy(
            reset_page_url=settings.password_reset_url,
            token_ttl=timedelta(minutes=settings.password_reset_ttl_minutes),
        ),
        clock=clock,
    )


def get_reset_password_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    token_generator: Annotated[
        OpaqueTokenGenerator, Depends(get_token_generator)
    ],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    password_policy: Annotated[PasswordPolicy, Depends(get_password_policy)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ResetPasswordUseCase:
    """Provide the password reset use case.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.
    token_generator : OpaqueTokenGenerator
        Hashes reset tokens.
    password_hasher : PasswordHasher
        Hashes the new password.
    password_policy : PasswordPolicy
        Password strength rules.
    clock : Clock
        Source of the current time.

    Returns
    -------
    ResetPasswordUseCase
        Configured use case.
    """
    return ResetPasswordUseCase(
        unit_of_work=unit_of_work,
        token_generator=token_generator,
        password_hasher=password_hasher,
        password_policy=password_policy,
        clock=clock,
    )


def get_change_password_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    password_policy: Annotated[PasswordPolicy, Depends(get_password_policy)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ChangePasswordUseCase:
    """Provide the password change use case.

    Parameters
    ----------
    unit_of_work : UnitOfWork
        Transaction boundary.
    password_hasher : PasswordHasher
        Verifies and hashes passwords.
    password_policy : PasswordPolicy
        Password strength rules.
    clock : Clock
        Source of the current time.

    Returns
    -------
    ChangePasswordUseCase
        Configured use case.
    """
    return ChangePasswordUseCase(
        unit_of_work=unit_of_work,
        password_hasher=password_hasher,
        password_policy=password_policy,
        clock=clock,
    )


def get_request_context(request: Request) -> RequestContext:
    """Provide the client information of the current request.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    RequestContext
        IP address and user agent of the client.
    """
    return build_request_context(request)


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
        Validates the token against the stored session.

    Returns
    -------
    AuthenticatedPrincipal
        The authenticated user and session.

    Raises
    ------
    InvalidAccessTokenError
        When the header is missing or the token is not valid.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidAccessTokenError()
    return authenticate_use_case.execute(credentials.credentials)
