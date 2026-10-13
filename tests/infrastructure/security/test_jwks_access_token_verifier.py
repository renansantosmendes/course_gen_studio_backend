"""Tests of the verifier of auth service tokens."""

from datetime import timedelta

import jwt
import pytest

from coursegen_backend.domain.exceptions import (
    AuthServiceUnavailableError,
    InvalidAccessTokenError,
)
from coursegen_backend.infrastructure.security import (
    jwks_access_token_verifier,
)
from coursegen_backend.infrastructure.security.jwks_access_token_verifier import (
    JwksAccessTokenVerifier,
    build_jwks_key_resolver,
)
from tests.conftest import AUDIENCE, ISSUER, OTHER_SIGNING_KEY, issue_token
from tests.fakes import make_identity


def test_valid_token_returns_identity(
    access_token_verifier: JwksAccessTokenVerifier,
) -> None:
    """Identifier, e-mail and name come from the claims.

    Parameters
    ----------
    access_token_verifier : JwksAccessTokenVerifier
        Verifier trusting the test key.

    Returns
    -------
    None
    """
    identity = make_identity()
    assert access_token_verifier.verify(issue_token(identity)) == identity


@pytest.mark.parametrize(
    "token_arguments",
    [
        {"lifetime": timedelta(minutes=-1)},
        {"signing_key": OTHER_SIGNING_KEY},
        {"iss": "someone-else"},
        {"aud": "other-app"},
        {"typ": "refresh"},
        {"email": None},
        {"name": None},
        {"sub": "not-a-uuid"},
    ],
)
def test_untrusted_tokens_are_refused(
    access_token_verifier: JwksAccessTokenVerifier,
    token_arguments: dict,
) -> None:
    """Expired, foreign, wrong-audience or incomplete tokens fail.

    Parameters
    ----------
    access_token_verifier : JwksAccessTokenVerifier
        Verifier trusting the test key.
    token_arguments : dict
        Changes that make the token untrustworthy.

    Returns
    -------
    None
    """
    token = issue_token(make_identity(), **token_arguments)
    with pytest.raises(InvalidAccessTokenError):
        access_token_verifier.verify(token)


def test_unreachable_jwks_is_reported_as_unavailable() -> None:
    """Failing to download keys is not blamed on the token."""

    def failing_resolver(_token: str) -> None:
        """Simulate an unreachable auth service.

        Parameters
        ----------
        _token : str
            Token being verified.

        Returns
        -------
        None
        """
        raise jwt.PyJWKClientConnectionError("connection refused")

    verifier = JwksAccessTokenVerifier(
        signing_key_resolver=failing_resolver,
        issuer=ISSUER,
        audience=AUDIENCE,
    )
    with pytest.raises(AuthServiceUnavailableError):
        verifier.verify(issue_token(make_identity()))


def test_key_resolver_is_cached_per_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One JWKS client per URL is kept for the whole process.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Records the JWKS clients created.

    Returns
    -------
    None
    """
    created_urls = []

    class RecordingClient:
        """Stand-in for ``jwt.PyJWKClient``."""

        def __init__(
            self,
            url: str,
            **_options: object,
        ) -> None:
            """Record the URL.

            Parameters
            ----------
            url : str
                JWKS address.
            **_options : object
                Ignored client options.

            Returns
            -------
            None
            """
            created_urls.append(url)

    build_jwks_key_resolver.cache_clear()
    monkeypatch.setattr(jwks_access_token_verifier.jwt, "PyJWKClient", RecordingClient)
    first = build_jwks_key_resolver("https://auth.example.com/.well-known/jwks.json")
    second = build_jwks_key_resolver("https://auth.example.com/.well-known/jwks.json")
    assert first is second
    assert created_urls == ["https://auth.example.com/.well-known/jwks.json"]
    build_jwks_key_resolver.cache_clear()
