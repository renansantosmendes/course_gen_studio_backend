"""Shared fixtures and token helpers of the test suite."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from coursegen_backend.domain.entities import VerifiedIdentity
from coursegen_backend.infrastructure.security.jwks_access_token_verifier import (
    JwksAccessTokenVerifier,
)
from tests.fakes import InMemoryUnitOfWork

ISSUER = "auth-service"
AUDIENCE = "synapse-apps"
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_SIGNING_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)


def issue_token(
    identity: VerifiedIdentity,
    signing_key: Any = SIGNING_KEY,
    lifetime: timedelta = timedelta(minutes=15),
    **claim_overrides: Any,
) -> str:
    """Sign a token in the format issued by the auth service.

    Parameters
    ----------
    identity : VerifiedIdentity
        Account the token is issued to.
    signing_key : Any
        RSA private key that signs the token.
    lifetime : timedelta
        Time until expiration; negative for an expired token.
    **claim_overrides : Any
        Claims to replace, or to remove when given as ``None``.

    Returns
    -------
    str
        Encoded RS256 token.
    """
    now = datetime.now(UTC)
    claims = {
        "sub": str(identity.user_id),
        "sid": "00000000-0000-0000-0000-000000000001",
        "email": identity.email,
        "name": identity.full_name,
        "typ": "access",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + lifetime,
    }
    claims.update(claim_overrides)
    claims = {key: value for key, value in claims.items() if value is not None}
    return jwt.encode(
        claims,
        signing_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


@pytest.fixture
def unit_of_work() -> InMemoryUnitOfWork:
    """Provide an in-memory unit of work.

    Returns
    -------
    InMemoryUnitOfWork
        Empty unit of work.
    """
    return InMemoryUnitOfWork()


@pytest.fixture
def access_token_verifier() -> JwksAccessTokenVerifier:
    """Provide a verifier that trusts the test signing key.

    Returns
    -------
    JwksAccessTokenVerifier
        Verifier whose key resolver returns the test public key.
    """
    return JwksAccessTokenVerifier(
        signing_key_resolver=lambda _token: SIGNING_KEY.public_key(),
        issuer=ISSUER,
        audience=AUDIENCE,
    )
