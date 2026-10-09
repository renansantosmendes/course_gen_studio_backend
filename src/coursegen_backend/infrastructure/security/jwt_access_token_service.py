"""Access tokens encoded as signed JSON Web Tokens."""

from datetime import datetime, timedelta
from uuid import UUID

import jwt

from coursegen_backend.application.ports.security import (
    AccessTokenClaims,
    AccessTokenService,
    IssuedAccessToken,
)
from coursegen_backend.domain.exceptions import InvalidAccessTokenError

ACCESS_TOKEN_TYPE = "access"


class JwtAccessTokenService(AccessTokenService):
    """Issues HS256-signed JWT access tokens."""

    def __init__(
        self,
        secret_key: str,
        time_to_live: timedelta,
        issuer: str,
        algorithm: str = "HS256",
    ) -> None:
        """Create the service.

        Parameters
        ----------
        secret_key : str
            Key used to sign and verify the tokens.
        time_to_live : timedelta
            Lifetime of each access token.
        issuer : str
            Value of the ``iss`` claim, checked on decoding.
        algorithm : str
            Signing algorithm.

        Returns
        -------
        None
        """
        self._secret_key = secret_key
        self._time_to_live = time_to_live
        self._issuer = issuer
        self._algorithm = algorithm

    def issue(
        self,
        user_id: UUID,
        session_id: UUID,
        issued_at: datetime,
    ) -> IssuedAccessToken:
        """Issue a signed access token.

        Parameters
        ----------
        user_id : UUID
            User the token is issued to (``sub`` claim).
        session_id : UUID
            Session the token belongs to (``sid`` claim).
        issued_at : datetime
            Moment of issue (``iat`` claim).

        Returns
        -------
        IssuedAccessToken
            The encoded token and its expiration moment.
        """
        expires_at = issued_at + self._time_to_live
        token = jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "typ": ACCESS_TOKEN_TYPE,
                "iss": self._issuer,
                "iat": issued_at,
                "exp": expires_at,
            },
            self._secret_key,
            algorithm=self._algorithm,
        )
        return IssuedAccessToken(token=token, expires_at=expires_at)

    def decode(
        self,
        token: str,
    ) -> AccessTokenClaims:
        """Validate a token and extract its claims.

        Parameters
        ----------
        token : str
            Encoded access token.

        Returns
        -------
        AccessTokenClaims
            User and session of the token.

        Raises
        ------
        InvalidAccessTokenError
            When the signature, issuer, type or expiration is invalid,
            or a required claim is missing.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={"require": ["sub", "sid", "exp", "iat", "iss"]},
            )
            if payload.get("typ") != ACCESS_TOKEN_TYPE:
                raise InvalidAccessTokenError()
            return AccessTokenClaims(
                user_id=UUID(payload["sub"]),
                session_id=UUID(payload["sid"]),
            )
        except (jwt.PyJWTError, ValueError) as error:
            raise InvalidAccessTokenError() from error
