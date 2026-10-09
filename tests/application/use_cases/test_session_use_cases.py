"""Tests of the refresh, authenticate, profile and logout use cases."""

from dataclasses import replace
from datetime import timedelta

import pytest

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import (
    RequestContext,
    SessionTokens,
)
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.application.use_cases.authenticate import (
    AuthenticateUseCase,
)
from coursegen_backend.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from coursegen_backend.application.use_cases.logout import LogoutUseCase
from coursegen_backend.application.use_cases.refresh_session import (
    RefreshSessionUseCase,
)
from coursegen_backend.domain.entities import User
from coursegen_backend.domain.exceptions import (
    InvalidAccessTokenError,
    InvalidRefreshTokenError,
)
from coursegen_backend.infrastructure.security.jwt_access_token_service import (
    JwtAccessTokenService,
)
from coursegen_backend.infrastructure.security.opaque_token_generator import (
    SecretsOpaqueTokenGenerator,
)
from tests.fakes import (
    FakeClock,
    InMemoryUnitOfWork,
    make_membership,
    make_user,
)


def open_session(
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
    user: User,
) -> SessionTokens:
    """Store a user and open a session for them.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.
    user : User
        User to store.

    Returns
    -------
    SessionTokens
        Credentials of the new session.
    """
    unit_of_work.users.add(user, [make_membership()])
    return session_token_issuer.open_session(
        unit_of_work=unit_of_work,
        user=user,
        keep_signed_in=False,
        context=RequestContext(),
        moment=clock.now(),
    )


@pytest.fixture
def refresh_use_case(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> RefreshSessionUseCase:
    """Provide the refresh use case.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    RefreshSessionUseCase
        Use case under test.
    """
    return RefreshSessionUseCase(
        unit_of_work=unit_of_work,
        token_generator=token_generator,
        session_token_issuer=session_token_issuer,
        clock=clock,
    )


@pytest.fixture
def authenticate_use_case(
    unit_of_work: InMemoryUnitOfWork,
    access_token_service: JwtAccessTokenService,
    clock: FakeClock,
) -> AuthenticateUseCase:
    """Provide the authenticate use case.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    access_token_service : JwtAccessTokenService
        Access token service.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    AuthenticateUseCase
        Use case under test.
    """
    return AuthenticateUseCase(
        unit_of_work=unit_of_work,
        access_token_service=access_token_service,
        clock=clock,
    )


def test_refresh_rotates_token(
    refresh_use_case: RefreshSessionUseCase,
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """A refresh returns new tokens and the old refresh token dies.

    Parameters
    ----------
    refresh_use_case : RefreshSessionUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    tokens = open_session(
        unit_of_work,
        session_token_issuer,
        clock,
        make_user(),
    )
    renewed = refresh_use_case.execute(tokens.refresh_token)
    assert renewed.session_id == tokens.session_id
    assert renewed.refresh_token != tokens.refresh_token
    with pytest.raises(InvalidRefreshTokenError):
        refresh_use_case.execute(tokens.refresh_token)


def test_refresh_rejects_unknown_and_expired_tokens(
    refresh_use_case: RefreshSessionUseCase,
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """Unknown tokens and expired sessions cannot be refreshed.

    Parameters
    ----------
    refresh_use_case : RefreshSessionUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    with pytest.raises(InvalidRefreshTokenError):
        refresh_use_case.execute("unknown-token")
    tokens = open_session(
        unit_of_work,
        session_token_issuer,
        clock,
        make_user(),
    )
    clock.advance(timedelta(hours=13))
    with pytest.raises(InvalidRefreshTokenError):
        refresh_use_case.execute(tokens.refresh_token)


def test_refresh_of_deactivated_account_revokes_session(
    refresh_use_case: RefreshSessionUseCase,
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """Deactivated accounts lose their sessions on the next refresh.

    Parameters
    ----------
    refresh_use_case : RefreshSessionUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = make_user()
    tokens = open_session(unit_of_work, session_token_issuer, clock, user)
    unit_of_work.users.add(replace(user, is_active=False))
    with pytest.raises(InvalidRefreshTokenError):
        refresh_use_case.execute(tokens.refresh_token)
    assert unit_of_work.sessions.get_by_id(tokens.session_id).revoked_at


def test_authenticate_resolves_principal(
    authenticate_use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """A valid access token resolves to its user and session.

    Parameters
    ----------
    authenticate_use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = make_user()
    tokens = open_session(unit_of_work, session_token_issuer, clock, user)
    principal = authenticate_use_case.execute(tokens.access_token)
    assert principal.user.id == user.id
    assert principal.session_id == tokens.session_id


def test_authenticate_rejects_revoked_session(
    authenticate_use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """Access tokens die together with their session.

    Parameters
    ----------
    authenticate_use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    tokens = open_session(
        unit_of_work,
        session_token_issuer,
        clock,
        make_user(),
    )
    unit_of_work.sessions.revoke(tokens.session_id, clock.now())
    with pytest.raises(InvalidAccessTokenError):
        authenticate_use_case.execute(tokens.access_token)


def test_authenticate_rejects_malformed_token(
    authenticate_use_case: AuthenticateUseCase,
) -> None:
    """Garbage tokens are rejected before touching storage.

    Parameters
    ----------
    authenticate_use_case : AuthenticateUseCase
        Use case under test.

    Returns
    -------
    None
    """
    with pytest.raises(InvalidAccessTokenError):
        authenticate_use_case.execute("not-a-jwt")


def test_profile_and_logout(
    authenticate_use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """The profile lists memberships; logout revokes the session.

    Parameters
    ----------
    authenticate_use_case : AuthenticateUseCase
        Authenticate use case.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    tokens = open_session(
        unit_of_work,
        session_token_issuer,
        clock,
        make_user(),
    )
    principal = authenticate_use_case.execute(tokens.access_token)
    profile = GetCurrentUserProfileUseCase(unit_of_work).execute(principal)
    assert profile.memberships[0].roles == ("author", "reviewer")
    LogoutUseCase(unit_of_work, clock).execute(principal, RequestContext())
    assert unit_of_work.audit_log.actions == [audit_actions.LOGOUT]
    with pytest.raises(InvalidAccessTokenError):
        authenticate_use_case.execute(tokens.access_token)
