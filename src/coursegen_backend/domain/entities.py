"""Domain entities of the authentication context."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    """A person who can sign in to CourseGen Studio.

    Attributes
    ----------
    id : UUID
        Unique identifier of the user.
    email : str
        Institutional e-mail address, unique and case-insensitive.
    full_name : str
        Name displayed in the interface.
    job_title : str | None
        Optional job title, for example "Instructional designer".
    password_hash : str | None
        Hash of the password, or ``None`` when the account signs in only
        through an external identity provider.
    is_active : bool
        Whether the account is allowed to sign in.
    last_login_at : datetime | None
        Moment of the last successful sign-in, if any.
    """

    id: UUID
    email: str
    full_name: str
    job_title: str | None
    password_hash: str | None
    is_active: bool
    last_login_at: datetime | None

    @property
    def can_sign_in_with_password(self) -> bool:
        """Tell whether the user may authenticate with a password.

        Returns
        -------
        bool
            ``True`` when the account is active and has a password set.
        """
        return self.is_active and self.password_hash is not None


@dataclass(frozen=True)
class OrganizationMembership:
    """The roles a user holds inside one organization (tenant).

    Attributes
    ----------
    organization_id : UUID
        Identifier of the organization.
    organization_name : str
        Display name of the organization.
    organization_slug : str
        URL-friendly unique name of the organization.
    roles : tuple[str, ...]
        Roles of the user in the organization: ``author``, ``reviewer``,
        ``curator`` and/or ``admin``.
    """

    organization_id: UUID
    organization_name: str
    organization_slug: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class UserSession:
    """A signed-in session, renewed through a refresh token.

    Attributes
    ----------
    id : UUID
        Identifier of the session, embedded in the access tokens.
    user_id : UUID
        Owner of the session.
    keep_signed_in : bool
        Whether the user asked to stay signed in on this device, which
        gives the session a longer lifetime.
    created_at : datetime
        Moment the session was opened.
    expires_at : datetime
        Moment after which the refresh token is no longer accepted.
    revoked_at : datetime | None
        Moment the session was ended, if it was.
    """

    id: UUID
    user_id: UUID
    keep_signed_in: bool
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    def is_active(
        self,
        moment: datetime,
    ) -> bool:
        """Tell whether the session can still be used at a given moment.

        Parameters
        ----------
        moment : datetime
            Timezone-aware moment to evaluate.

        Returns
        -------
        bool
            ``True`` when the session is neither revoked nor expired.
        """
        return self.revoked_at is None and moment < self.expires_at


@dataclass(frozen=True)
class PasswordResetToken:
    """A single-use permission to define a new password.

    Attributes
    ----------
    id : UUID
        Identifier of the token record.
    user_id : UUID
        User whose password may be reset.
    expires_at : datetime
        Moment after which the token is no longer accepted.
    used_at : datetime | None
        Moment the token was consumed, if it was.
    """

    id: UUID
    user_id: UUID
    expires_at: datetime
    used_at: datetime | None

    def is_usable(
        self,
        moment: datetime,
    ) -> bool:
        """Tell whether the token can still be redeemed at a given moment.

        Parameters
        ----------
        moment : datetime
            Timezone-aware moment to evaluate.

        Returns
        -------
        bool
            ``True`` when the token is neither used nor expired.
        """
        return self.used_at is None and moment < self.expires_at
