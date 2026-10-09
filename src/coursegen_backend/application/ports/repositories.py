"""Persistence ports of the authentication context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from coursegen_backend.domain.entities import (
    OrganizationMembership,
    PasswordResetToken,
    User,
    UserSession,
)


@dataclass(frozen=True)
class AuditEvent:
    """An entry of the audit trail.

    Attributes
    ----------
    action : str
        What happened, for example ``auth.login``.
    actor_user_id : UUID | None
        User who performed the action, when known.
    entity_type : str | None
        Kind of the affected record, for example ``user``.
    entity_id : UUID | None
        Identifier of the affected record.
    details : dict[str, Any]
        Additional JSON-serializable information.
    ip_address : str | None
        IP address of the client.
    """

    action: str
    actor_user_id: UUID | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None


class UserRepository(ABC):
    """Reads and updates user accounts."""

    @abstractmethod
    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        """Find a user by e-mail, ignoring letter case.

        Parameters
        ----------
        email : str
            E-mail address.

        Returns
        -------
        User | None
            The user, or ``None`` when no account uses the e-mail.
        """

    @abstractmethod
    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        """Find a user by identifier.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        User | None
            The user, or ``None`` when it does not exist.
        """

    @abstractmethod
    def update_password_hash(
        self,
        user_id: UUID,
        password_hash: str,
    ) -> None:
        """Replace the stored password hash of a user.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        password_hash : str
            New password hash.

        Returns
        -------
        None
        """

    @abstractmethod
    def update_last_login(
        self,
        user_id: UUID,
        moment: datetime,
    ) -> None:
        """Record the moment of a successful sign-in.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        moment : datetime
            Moment of the sign-in.

        Returns
        -------
        None
        """

    @abstractmethod
    def list_memberships(
        self,
        user_id: UUID,
    ) -> list[OrganizationMembership]:
        """List the organizations of a user and the roles held in each.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        list[OrganizationMembership]
            Memberships ordered by organization name.
        """


class SessionRepository(ABC):
    """Stores signed-in sessions and their refresh token hashes."""

    @abstractmethod
    def create(
        self,
        user_id: UUID,
        refresh_token_hash: str,
        keep_signed_in: bool,
        user_agent: str | None,
        ip_address: str | None,
        expires_at: datetime,
    ) -> UserSession:
        """Open a new session.

        Parameters
        ----------
        user_id : UUID
            Owner of the session.
        refresh_token_hash : str
            Hash of the refresh token given to the client.
        keep_signed_in : bool
            Whether the session uses the long lifetime.
        user_agent : str | None
            User agent of the client.
        ip_address : str | None
            IP address of the client.
        expires_at : datetime
            Expiration moment of the refresh token.

        Returns
        -------
        UserSession
            The stored session.
        """

    @abstractmethod
    def get_by_id(
        self,
        session_id: UUID,
    ) -> UserSession | None:
        """Find a session by identifier.

        Parameters
        ----------
        session_id : UUID
            Identifier of the session.

        Returns
        -------
        UserSession | None
            The session, or ``None`` when it does not exist.
        """

    @abstractmethod
    def get_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> UserSession | None:
        """Find the session that owns a refresh token.

        Parameters
        ----------
        refresh_token_hash : str
            Hash of the refresh token.

        Returns
        -------
        UserSession | None
            The session, or ``None`` when no session owns the token.
        """

    @abstractmethod
    def rotate_refresh_token(
        self,
        session_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> UserSession:
        """Replace the refresh token of a session and extend it.

        Parameters
        ----------
        session_id : UUID
            Identifier of the session.
        refresh_token_hash : str
            Hash of the new refresh token.
        expires_at : datetime
            New expiration moment.

        Returns
        -------
        UserSession
            The updated session.
        """

    @abstractmethod
    def revoke(
        self,
        session_id: UUID,
        moment: datetime,
    ) -> None:
        """End a session, if it is not ended yet.

        Parameters
        ----------
        session_id : UUID
            Identifier of the session.
        moment : datetime
            Moment of revocation.

        Returns
        -------
        None
        """

    @abstractmethod
    def revoke_all_for_user(
        self,
        user_id: UUID,
        moment: datetime,
        except_session_id: UUID | None = None,
    ) -> int:
        """End every open session of a user.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        moment : datetime
            Moment of revocation.
        except_session_id : UUID | None
            Session to keep open, typically the current one.

        Returns
        -------
        int
            Number of sessions ended.
        """


class PasswordResetTokenRepository(ABC):
    """Stores password reset tokens as hashes."""

    @abstractmethod
    def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Store a new reset token.

        Parameters
        ----------
        user_id : UUID
            User whose password may be reset.
        token_hash : str
            Hash of the token sent by e-mail.
        expires_at : datetime
            Expiration moment.

        Returns
        -------
        PasswordResetToken
            The stored token.
        """

    @abstractmethod
    def get_by_token_hash(
        self,
        token_hash: str,
    ) -> PasswordResetToken | None:
        """Find a reset token by its hash.

        Parameters
        ----------
        token_hash : str
            Hash of the token.

        Returns
        -------
        PasswordResetToken | None
            The token, or ``None`` when it does not exist.
        """

    @abstractmethod
    def invalidate_all_for_user(
        self,
        user_id: UUID,
        moment: datetime,
    ) -> None:
        """Mark every unused reset token of a user as used.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        moment : datetime
            Moment recorded as the use time.

        Returns
        -------
        None
        """


class AuditLogRepository(ABC):
    """Append-only audit trail."""

    @abstractmethod
    def record(
        self,
        event: AuditEvent,
    ) -> None:
        """Append an event to the audit trail.

        Parameters
        ----------
        event : AuditEvent
            Event to record.

        Returns
        -------
        None
        """

    @abstractmethod
    def count_for_entity_since(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        since: datetime,
    ) -> int:
        """Count events of an action on a record after a moment.

        Parameters
        ----------
        action : str
            Action to count, for example ``auth.login_failed``.
        entity_type : str
            Kind of the affected record.
        entity_id : UUID
            Identifier of the affected record.
        since : datetime
            Only events created at or after this moment are counted.

        Returns
        -------
        int
            Number of matching events.
        """
