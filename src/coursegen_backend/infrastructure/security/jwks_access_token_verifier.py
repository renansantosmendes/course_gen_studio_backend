"""Verification of auth service tokens with its published public keys."""

from collections.abc import Callable
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt

from coursegen_backend.application.ports.security import AccessTokenVerifier
from coursegen_backend.domain.entities import VerifiedIdentity
from coursegen_backend.domain.exceptions import (
    AuthServiceUnavailableError,
    InvalidAccessTokenError,
)

ACCESS_TOKEN_TYPE = "access"
SIGNING_ALGORITHM = "RS256"
JWKS_CACHE_SECONDS = 3600
REQUIRED_CLAIMS = ["sub", "email", "name", "exp", "iat", "iss", "aud"]

SigningKeyResolver = Callable[[str], Any]


@lru_cache(maxsize=4)
def build_jwks_key_resolver(jwks_url: str) -> SigningKeyResolver:
    """Create a resolver that picks the signing key of a token by ``kid``.

    The JWKS is downloaded on first use and cached for an hour, and the
    resolver itself is cached per URL, so a warm serverless instance does
    not download the keys on every request.

    Parameters
    ----------
    jwks_url : str
        Address of the auth service's ``/.well-known/jwks.json``.

    Returns
    -------
    SigningKeyResolver
        Function that returns the public key matching a token's ``kid``.
    """
    client = jwt.PyJWKClient(
        jwks_url,
        cache_keys=True,
        lifespan=JWKS_CACHE_SECONDS,
        timeout=10,
    )
    return lambda token: client.get_signing_key_from_jwt(token).key


class JwksAccessTokenVerifier(AccessTokenVerifier):
    """Verifies RS256 access tokens issued by the auth service.

    Checks the signature against the auth service's public keys, the
    expiration, the issuer, the audience and the token type. CourseGen
    never holds a key able to issue tokens.
    """

    def __init__(
        self,
        signing_key_resolver: SigningKeyResolver,
        issuer: str,
        audience: str,
    ) -> None:
        """Create the verifier.

        Parameters
        ----------
        signing_key_resolver : SigningKeyResolver
            Returns the public key that must have signed a given token.
        issuer : str
            Expected ``iss`` claim.
        audience : str
            Expected ``aud`` claim.

        Returns
        -------
        None
        """
        self._signing_key_resolver = signing_key_resolver
        self._issuer = issuer
        self._audience = audience

    def verify(
        self,
        token: str,
    ) -> VerifiedIdentity:
        """Validate a token and return the identity it was issued to.

        Parameters
        ----------
        token : str
            Encoded access token.

        Returns
        -------
        VerifiedIdentity
            Identifier, e-mail and name of the account.

        Raises
        ------
        InvalidAccessTokenError
            When the token is malformed, expired, signed by an unknown
            key, issued by someone else, for another audience, or is not
            an access token.
        AuthServiceUnavailableError
            When the public keys cannot be downloaded.
        """
        try:
            payload = jwt.decode(
                token,
                self._signing_key_resolver(token),
                algorithms=[SIGNING_ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": REQUIRED_CLAIMS},
            )
            if payload.get("typ") != ACCESS_TOKEN_TYPE:
                raise InvalidAccessTokenError()
            return VerifiedIdentity(
                user_id=UUID(payload["sub"]),
                email=payload["email"],
                full_name=payload["name"],
            )
        except jwt.PyJWKClientConnectionError as error:
            raise AuthServiceUnavailableError() from error
        except (jwt.PyJWTError, ValueError, KeyError) as error:
            raise InvalidAccessTokenError() from error
