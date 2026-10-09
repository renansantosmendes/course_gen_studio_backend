"""Tests of the session token issuer."""

from datetime import timedelta

from coursegen_backend.application.dto import RequestContext
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.infrastructure.security.jwt_access_token_service import (
    JwtAccessTokenService,
)
from coursegen_backend.infrastructure.security.opaque_token_generator import (
    SecretsOpaqueTokenGenerator,
)
from tests.fakes import FakeClock, InMemoryUnitOfWork, make_user


def test_open_session_stores_hash_and_issues_tokens(
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    access_token_service: JwtAccessTokenService,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
) -> None:
    """Only the refresh token hash is stored; the JWT names the session.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Issuer under test.
    access_token_service : JwtAccessTokenService
        Decodes the issued access token.
    token_generator : SecretsOpaqueTokenGenerator
        Hashes the refresh token.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = make_user()
    tokens = session_token_issuer.open_session(
        unit_of_work=unit_of_work,
        user=user,
        keep_signed_in=False,
        context=RequestContext(ip_address="203.0.113.7"),
        moment=clock.now(),
    )
    stored_hash = unit_of_work.sessions.refresh_token_hashes[
        tokens.session_id
    ]
    assert stored_hash == token_generator.hash(tokens.refresh_token)
    assert stored_hash != tokens.refresh_token
    assert tokens.refresh_token_expires_at == clock.now() + timedelta(
        hours=12
    )
    claims = access_token_service.decode(tokens.access_token)
    assert claims.user_id == user.id
    assert claims.session_id == tokens.session_id


def test_keep_signed_in_uses_long_lifetime(
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """Sessions that stay signed in last 30 days by default.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Issuer under test.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    tokens = session_token_issuer.open_session(
        unit_of_work=unit_of_work,
        user=make_user(),
        keep_signed_in=True,
        context=RequestContext(),
        moment=clock.now(),
    )
    assert tokens.refresh_token_expires_at == clock.now() + timedelta(
        days=30
    )


def test_rotate_session_replaces_refresh_token(
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
) -> None:
    """Rotation keeps the session but changes its refresh token.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Issuer under test.
    token_generator : SecretsOpaqueTokenGenerator
        Hashes the refresh tokens.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    first = session_token_issuer.open_session(
        unit_of_work=unit_of_work,
        user=make_user(),
        keep_signed_in=False,
        context=RequestContext(),
        moment=clock.now(),
    )
    clock.advance(timedelta(hours=1))
    session = unit_of_work.sessions.get_by_id(first.session_id)
    second = session_token_issuer.rotate_session(
        unit_of_work=unit_of_work,
        session=session,
        moment=clock.now(),
    )
    assert second.session_id == first.session_id
    assert second.refresh_token != first.refresh_token
    assert unit_of_work.sessions.get_by_refresh_token_hash(
        token_generator.hash(first.refresh_token)
    ) is None
    assert second.refresh_token_expires_at == clock.now() + timedelta(
        hours=12
    )
