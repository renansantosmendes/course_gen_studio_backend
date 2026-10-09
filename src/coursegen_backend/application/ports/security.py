"""Ports for password hashing and token handling."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class IssuedAccessToken:
    """An access token and the moment it stops being valid.

    Attributes
    ----------
    token : str
        Encoded access token, sent as ``Authorization: Bearer <token>``.
    expires_at : datetime
        Moment the token expires.
    """

    token: str
    expires_at: datetime


@dataclass(frozen=True)
class AccessTokenClaims:
    """Information carried by a valid access token.

    Attributes
    ----------
    user_id : UUID
        User the token was issued to.
    session_id : UUID
        Session the token belongs to.
    """

    user_id: UUID
    session_id: UUID


class PasswordHasher(ABC):
    """Hashes passwords and checks passwords against hashes."""

    @abstractmethod
    def hash(
        self,
        password: str,
    ) -> str:
        """Compute a salted hash of a password.

        Parameters
        ----------
        password : str
            Password in plain text.

        Returns
        -------
        str
            Encoded hash, safe to store.
        """

    @abstractmethod
    def verify(
        self,
        password_hash: str,
        password: str,
    ) -> bool:
        """Check whether a password matches a stored hash.

        Parameters
        ----------
        password_hash : str
            Stored hash.
        password : str
            Password in plain text.

        Returns
        -------
        bool
            ``True`` when the password matches.
        """

    @abstractmethod
    def needs_rehash(
        self,
        password_hash: str,
    ) -> bool:
        """Tell whether a hash was produced with outdated parameters.

        Parameters
        ----------
        password_hash : str
            Stored hash.

        Returns
        -------
        bool
            ``True`` when the hash should be recomputed.
        """

    @abstractmethod
    def simulate_verification(
        self,
        password: str,
    ) -> None:
        """Spend the same time as a real verification, without a hash.

        Used when the account does not exist, so that response times do
        not reveal which e-mails are registered.

        Parameters
        ----------
        password : str
            Password in plain text.

        Returns
        -------
        None
        """


class AccessTokenService(ABC):
    """Issues and validates short-lived access tokens."""

    @abstractmethod
    def issue(
        self,
        user_id: UUID,
        session_id: UUID,
        issued_at: datetime,
    ) -> IssuedAccessToken:
        """Issue an access token for a session.

        Parameters
        ----------
        user_id : UUID
            User the token is issued to.
        session_id : UUID
            Session the token belongs to.
        issued_at : datetime
            Moment of issue.

        Returns
        -------
        IssuedAccessToken
            The encoded token and its expiration moment.
        """

    @abstractmethod
    def decode(
        self,
        token: str,
    ) -> AccessTokenClaims:
        """Validate an access token and extract its claims.

        Parameters
        ----------
        token : str
            Encoded access token.

        Returns
        -------
        AccessTokenClaims
            Claims of the token.

        Raises
        ------
        InvalidAccessTokenError
            When the token is malformed, tampered with or expired.
        """


class OpaqueTokenGenerator(ABC):
    """Creates random tokens that are stored only as hashes."""

    @abstractmethod
    def generate(self) -> str:
        """Create a new random token.

        Returns
        -------
        str
            URL-safe token, given once to the client.
        """

    @abstractmethod
    def hash(
        self,
        token: str,
    ) -> str:
        """Compute the deterministic hash under which a token is stored.

        Parameters
        ----------
        token : str
            Token in plain text.

        Returns
        -------
        str
            Hash of the token.
        """
