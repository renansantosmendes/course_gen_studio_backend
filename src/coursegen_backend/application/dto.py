"""Data structures exchanged between the use cases and their callers."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from coursegen_backend.domain.entities import OrganizationMembership, User


@dataclass(frozen=True)
class RequestContext:
    """Information about the client that triggered a use case.

    Attributes
    ----------
    ip_address : str | None
        Validated IP address of the client, when known.
    user_agent : str | None
        User agent reported by the client, when known.
    """

    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class SessionTokens:
    """Credentials handed to the client for a session.

    Attributes
    ----------
    session_id : UUID
        Identifier of the session.
    access_token : str
        Short-lived token for authenticated requests.
    access_token_expires_at : datetime
        Expiration moment of the access token.
    refresh_token : str
        Long-lived token used to obtain new access tokens.
    refresh_token_expires_at : datetime
        Expiration moment of the refresh token.
    """

    session_id: UUID
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime


@dataclass(frozen=True)
class UserProfile:
    """A user together with the organizations they belong to.

    Attributes
    ----------
    user : User
        The user account.
    memberships : list[OrganizationMembership]
        Organizations and roles of the user.
    """

    user: User
    memberships: list[OrganizationMembership]


@dataclass(frozen=True)
class LoginResult:
    """Outcome of a successful sign-in.

    Attributes
    ----------
    tokens : SessionTokens
        Credentials of the new session.
    profile : UserProfile
        The signed-in user.
    """

    tokens: SessionTokens
    profile: UserProfile


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """The user behind a validated access token.

    Attributes
    ----------
    user : User
        The authenticated user.
    session_id : UUID
        Session the access token belongs to.
    """

    user: User
    session_id: UUID
