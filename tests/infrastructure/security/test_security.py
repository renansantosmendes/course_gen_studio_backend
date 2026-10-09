"""Tests of the password hasher and the token implementations."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from coursegen_backend.domain.exceptions import InvalidAccessTokenError
from coursegen_backend.infrastructure.security.argon2_password_hasher import (
    Argon2PasswordHasher,
)
from coursegen_backend.infrastructure.security.jwt_access_token_service import (
    JwtAccessTokenService,
)
from coursegen_backend.infrastructure.security.opaque_token_generator import (
    SecretsOpaqueTokenGenerator,
)
from tests.conftest import TEST_JWT_SECRET
from tests.credentials import (
    OTHER_JWT_SECRET,
    VALID_PASSWORD,
)


@pytest.fixture(scope="module")
def hasher() -> Argon2PasswordHasher:
    """Provide a cheap Argon2 hasher for fast tests.

    Returns
    -------
    Argon2PasswordHasher
        Hasher with minimal cost parameters.
    """
    return Argon2PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


def test_argon2_hash_verifies_only_the_right_password(
    hasher: Argon2PasswordHasher,
) -> None:
    """Hashes are salted Argon2id and match only their password.

    Parameters
    ----------
    hasher : Argon2PasswordHasher
        Hasher under test.

    Returns
    -------
    None
    """
    password_hash = hasher.hash(VALID_PASSWORD)
    assert password_hash.startswith("$argon2id$")
    assert password_hash != hasher.hash(VALID_PASSWORD)
    assert hasher.verify(password_hash, VALID_PASSWORD)
    assert not hasher.verify(password_hash, "planejamento2026")


def test_argon2_handles_malformed_hash(
    hasher: Argon2PasswordHasher,
) -> None:
    """Malformed hashes never match and are flagged for rehash.

    Parameters
    ----------
    hasher : Argon2PasswordHasher
        Hasher under test.

    Returns
    -------
    None
    """
    assert not hasher.verify("not-a-hash", "anything")
    assert hasher.needs_rehash("not-a-hash")


def test_argon2_detects_outdated_parameters(
    hasher: Argon2PasswordHasher,
) -> None:
    """Hashes made with other parameters need a rehash.

    Parameters
    ----------
    hasher : Argon2PasswordHasher
        Hasher under test.

    Returns
    -------
    None
    """
    stronger = Argon2PasswordHasher(time_cost=2, memory_cost=8, parallelism=1)
    assert stronger.needs_rehash(hasher.hash(VALID_PASSWORD))
    assert not hasher.needs_rehash(hasher.hash(VALID_PASSWORD))
    hasher.simulate_verification("whatever")


def build_service(
    time_to_live: timedelta = timedelta(minutes=15),
) -> JwtAccessTokenService:
    """Create a JWT service with the test secret.

    Parameters
    ----------
    time_to_live : timedelta
        Token lifetime.

    Returns
    -------
    JwtAccessTokenService
        Service under test.
    """
    return JwtAccessTokenService(
        secret_key=TEST_JWT_SECRET,
        time_to_live=time_to_live,
        issuer="coursegen-studio",
    )


def test_jwt_round_trip() -> None:
    """Issued tokens decode to the same user and session."""
    user_id, session_id = uuid4(), uuid4()
    issued_at = datetime.now(UTC)
    issued = build_service().issue(user_id, session_id, issued_at)
    assert issued.expires_at == issued_at + timedelta(minutes=15)
    claims = build_service().decode(issued.token)
    assert (claims.user_id, claims.session_id) == (user_id, session_id)


def test_jwt_rejects_expired_token() -> None:
    """Tokens past their lifetime are refused."""
    issued = build_service().issue(
        uuid4(),
        uuid4(),
        datetime.now(UTC) - timedelta(hours=1),
    )
    with pytest.raises(InvalidAccessTokenError):
        build_service().decode(issued.token)


def test_jwt_rejects_other_secret_and_wrong_type() -> None:
    """Forged signatures and non-access tokens are refused."""
    now = datetime.now(UTC)
    foreign = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "typ": "access",
            "iss": "coursegen-studio",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        OTHER_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessTokenError):
        build_service().decode(foreign)
    wrong_type = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "typ": "refresh",
            "iss": "coursegen-studio",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessTokenError):
        build_service().decode(wrong_type)


def test_opaque_tokens_are_random_and_hash_deterministically() -> None:
    """Tokens differ every time; their hash is a stable SHA-256."""
    generator = SecretsOpaqueTokenGenerator()
    first, second = generator.generate(), generator.generate()
    assert first != second
    assert len(first) >= 64
    assert generator.hash(first) == generator.hash(first)
    assert len(generator.hash(first)) == 64
