"""In-memory test doubles for the application ports."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.email import (
    EmailDeliveryError,
    EmailMessage,
    EmailSender,
)
from coursegen_backend.application.ports.repositories import (
    AuditEvent,
    AuditLogRepository,
    PasswordResetTokenRepository,
    SessionRepository,
    UserRepository,
)
from coursegen_backend.application.ports.security import PasswordHasher
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.entities import (
    OrganizationMembership,
    PasswordResetToken,
    User,
    UserSession,
)
from tests.credentials import (
    TEST_EMAIL,
    VALID_PASSWORD,
)

DEFAULT_MOMENT = datetime.now(UTC).replace(microsecond=0)


class FakeClock(Clock):
    """Clock frozen at a moment that tests can move forward."""

    def __init__(
        self,
        moment: datetime = DEFAULT_MOMENT,
    ) -> None:
        """Create the clock.

        Parameters
        ----------
        moment : datetime
            Initial moment.

        Returns
        -------
        None
        """
        self.moment = moment

    def now(self) -> datetime:
        """Return the frozen moment.

        Returns
        -------
        datetime
            Current fake moment.
        """
        return self.moment

    def advance(
        self,
        delta: timedelta,
    ) -> None:
        """Move the clock forward.

        Parameters
        ----------
        delta : timedelta
            Amount of time to add.

        Returns
        -------
        None
        """
        self.moment = self.moment + delta


class FakePasswordHasher(PasswordHasher):
    """Reversible, instant hasher that records simulated checks."""

    def __init__(
        self,
        outdated_hashes: set[str] | None = None,
    ) -> None:
        """Create the hasher.

        Parameters
        ----------
        outdated_hashes : set[str] | None
            Hashes reported as needing a rehash.

        Returns
        -------
        None
        """
        self.outdated_hashes = outdated_hashes or set()
        self.simulated_verifications = 0

    def hash(
        self,
        password: str,
    ) -> str:
        """Return ``hashed:<password>``.

        Parameters
        ----------
        password : str
            Password in plain text.

        Returns
        -------
        str
            Fake hash.
        """
        return f"hashed:{password}"

    def verify(
        self,
        password_hash: str,
        password: str,
    ) -> bool:
        """Compare the password with the fake hash.

        Parameters
        ----------
        password_hash : str
            Fake or outdated hash.
        password : str
            Password in plain text.

        Returns
        -------
        bool
            ``True`` when the hash encodes the password.
        """
        return password_hash.split(":", 1)[-1] == password

    def needs_rehash(
        self,
        password_hash: str,
    ) -> bool:
        """Report hashes registered as outdated.

        Parameters
        ----------
        password_hash : str
            Stored hash.

        Returns
        -------
        bool
            ``True`` for outdated hashes.
        """
        return password_hash in self.outdated_hashes

    def simulate_verification(
        self,
        password: str,
    ) -> None:
        """Count the simulated verification.

        Parameters
        ----------
        password : str
            Password in plain text.

        Returns
        -------
        None
        """
        self.simulated_verifications += 1


class RecordingEmailSender(EmailSender):
    """Keeps the sent messages in a list, optionally failing."""

    def __init__(
        self,
        should_fail: bool = False,
    ) -> None:
        """Create the sender.

        Parameters
        ----------
        should_fail : bool
            Whether ``send`` raises instead of recording.

        Returns
        -------
        None
        """
        self.should_fail = should_fail
        self.messages = []

    def send(
        self,
        message: EmailMessage,
    ) -> None:
        """Record the message or raise.

        Parameters
        ----------
        message : EmailMessage
            Message to record.

        Returns
        -------
        None
        """
        if self.should_fail:
            raise EmailDeliveryError("SMTP server unavailable")
        self.messages.append(message)


class InMemoryUserRepository(UserRepository):
    """User repository backed by dictionaries."""

    def __init__(self) -> None:
        """Create an empty repository.

        Returns
        -------
        None
        """
        self.users = {}
        self.memberships = {}

    def add(
        self,
        user: User,
        memberships: list[OrganizationMembership] | None = None,
    ) -> User:
        """Store a user for the test.

        Parameters
        ----------
        user : User
            User to store.
        memberships : list[OrganizationMembership] | None
            Organizations of the user.

        Returns
        -------
        User
            The stored user.
        """
        self.users[user.id] = user
        self.memberships[user.id] = memberships or []
        return user

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        """Find a user by e-mail, ignoring case.

        Parameters
        ----------
        email : str
            E-mail address.

        Returns
        -------
        User | None
            The user, if any.
        """
        return next(
            (
                user
                for user in self.users.values()
                if user.email.casefold() == email.casefold()
            ),
            None,
        )

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
            The user, if any.
        """
        return self.users.get(user_id)

    def update_password_hash(
        self,
        user_id: UUID,
        password_hash: str,
    ) -> None:
        """Replace the password hash.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        password_hash : str
            New hash.

        Returns
        -------
        None
        """
        self.users[user_id] = replace(
            self.users[user_id],
            password_hash=password_hash,
        )

    def update_last_login(
        self,
        user_id: UUID,
        moment: datetime,
    ) -> None:
        """Record the last sign-in moment.

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
        self.users[user_id] = replace(
            self.users[user_id],
            last_login_at=moment,
        )

    def list_memberships(
        self,
        user_id: UUID,
    ) -> list[OrganizationMembership]:
        """Return the stored memberships.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        list[OrganizationMembership]
            Memberships of the user.
        """
        return list(self.memberships.get(user_id, []))


class InMemorySessionRepository(SessionRepository):
    """Session repository backed by dictionaries."""

    def __init__(
        self,
        clock: Clock,
    ) -> None:
        """Create an empty repository.

        Parameters
        ----------
        clock : Clock
            Source of ``created_at``.

        Returns
        -------
        None
        """
        self._clock = clock
        self.sessions = {}
        self.refresh_token_hashes = {}

    def create(
        self,
        user_id: UUID,
        refresh_token_hash: str,
        keep_signed_in: bool,
        user_agent: str | None,
        ip_address: str | None,
        expires_at: datetime,
    ) -> UserSession:
        """Store a new session.

        Parameters
        ----------
        user_id : UUID
            Owner.
        refresh_token_hash : str
            Hash of the refresh token.
        keep_signed_in : bool
            Long lifetime flag.
        user_agent : str | None
            User agent.
        ip_address : str | None
            IP address.
        expires_at : datetime
            Expiration moment.

        Returns
        -------
        UserSession
            The stored session.
        """
        session = UserSession(
            id=uuid4(),
            user_id=user_id,
            keep_signed_in=keep_signed_in,
            created_at=self._clock.now(),
            expires_at=expires_at,
            revoked_at=None,
        )
        self.sessions[session.id] = session
        self.refresh_token_hashes[session.id] = refresh_token_hash
        return session

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
            The session, if any.
        """
        return self.sessions.get(session_id)

    def get_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> UserSession | None:
        """Find the session owning a refresh token hash.

        Parameters
        ----------
        refresh_token_hash : str
            Hash of the refresh token.

        Returns
        -------
        UserSession | None
            The session, if any.
        """
        for session_id, stored_hash in self.refresh_token_hashes.items():
            if stored_hash == refresh_token_hash:
                return self.sessions[session_id]
        return None

    def rotate_refresh_token(
        self,
        session_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> UserSession:
        """Replace the refresh token hash and expiration.

        Parameters
        ----------
        session_id : UUID
            Identifier of the session.
        refresh_token_hash : str
            New hash.
        expires_at : datetime
            New expiration moment.

        Returns
        -------
        UserSession
            The updated session.
        """
        self.refresh_token_hashes[session_id] = refresh_token_hash
        self.sessions[session_id] = replace(
            self.sessions[session_id],
            expires_at=expires_at,
        )
        return self.sessions[session_id]

    def revoke(
        self,
        session_id: UUID,
        moment: datetime,
    ) -> None:
        """Revoke a session if still open.

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
        session = self.sessions[session_id]
        if session.revoked_at is None:
            self.sessions[session_id] = replace(session, revoked_at=moment)

    def revoke_all_for_user(
        self,
        user_id: UUID,
        moment: datetime,
        except_session_id: UUID | None = None,
    ) -> int:
        """Revoke every active session of a user.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        moment : datetime
            Moment of revocation.
        except_session_id : UUID | None
            Session to keep open.

        Returns
        -------
        int
            Number of revoked sessions.
        """
        revoked = 0
        for session in list(self.sessions.values()):
            if (
                session.user_id == user_id
                and session.id != except_session_id
                and session.is_active(moment)
            ):
                self.sessions[session.id] = replace(
                    session,
                    revoked_at=moment,
                )
                revoked += 1
        return revoked


class InMemoryPasswordResetTokenRepository(PasswordResetTokenRepository):
    """Password reset token repository backed by dictionaries."""

    def __init__(self) -> None:
        """Create an empty repository.

        Returns
        -------
        None
        """
        self.tokens = {}

    def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Store a reset token.

        Parameters
        ----------
        user_id : UUID
            Owner.
        token_hash : str
            Hash of the token.
        expires_at : datetime
            Expiration moment.

        Returns
        -------
        PasswordResetToken
            The stored token.
        """
        token = PasswordResetToken(
            id=uuid4(),
            user_id=user_id,
            expires_at=expires_at,
            used_at=None,
        )
        self.tokens[token_hash] = token
        return token

    def get_by_token_hash(
        self,
        token_hash: str,
    ) -> PasswordResetToken | None:
        """Find a token by hash.

        Parameters
        ----------
        token_hash : str
            Hash of the token.

        Returns
        -------
        PasswordResetToken | None
            The token, if any.
        """
        return self.tokens.get(token_hash)

    def invalidate_all_for_user(
        self,
        user_id: UUID,
        moment: datetime,
    ) -> None:
        """Mark the unused tokens of a user as used.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.
        moment : datetime
            Use moment.

        Returns
        -------
        None
        """
        for token_hash, token in self.tokens.items():
            if token.user_id == user_id and token.used_at is None:
                self.tokens[token_hash] = replace(token, used_at=moment)


class InMemoryAuditLogRepository(AuditLogRepository):
    """Audit trail kept in a list of ``(event, created_at)`` pairs."""

    def __init__(
        self,
        clock: Clock,
    ) -> None:
        """Create an empty audit trail.

        Parameters
        ----------
        clock : Clock
            Source of ``created_at``.

        Returns
        -------
        None
        """
        self._clock = clock
        self.entries = []

    @property
    def actions(self) -> list[str]:
        """List the recorded actions in order.

        Returns
        -------
        list[str]
            Action names.
        """
        return [event.action for event, _ in self.entries]

    def record(
        self,
        event: AuditEvent,
    ) -> None:
        """Append an event.

        Parameters
        ----------
        event : AuditEvent
            Event to record.

        Returns
        -------
        None
        """
        self.entries.append((event, self._clock.now()))

    def count_for_entity_since(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        since: datetime,
    ) -> int:
        """Count matching events.

        Parameters
        ----------
        action : str
            Action to count.
        entity_type : str
            Kind of record.
        entity_id : UUID
            Identifier of the record.
        since : datetime
            Lower bound of ``created_at``.

        Returns
        -------
        int
            Number of matching events.
        """
        return sum(
            1
            for event, created_at in self.entries
            if event.action == action
            and event.entity_type == entity_type
            and event.entity_id == entity_id
            and created_at >= since
        )


class InMemoryUnitOfWork(UnitOfWork):
    """Unit of work over in-memory repositories that counts commits."""

    def __init__(
        self,
        clock: Clock,
    ) -> None:
        """Create the unit of work and its repositories.

        Parameters
        ----------
        clock : Clock
            Clock shared with the repositories.

        Returns
        -------
        None
        """
        self.users = InMemoryUserRepository()
        self.sessions = InMemorySessionRepository(clock)
        self.password_reset_tokens = InMemoryPasswordResetTokenRepository()
        self.audit_log = InMemoryAuditLogRepository(clock)
        self.commits = 0

    def __enter__(self) -> Self:
        """Begin the fake transaction.

        Returns
        -------
        Self
            The unit of work.
        """
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """End the fake transaction.

        Parameters
        ----------
        exception_type : type[BaseException] | None
            Type of the raised exception, if any.
        exception : BaseException | None
            Raised exception, if any.
        traceback : TracebackType | None
            Traceback, if any.

        Returns
        -------
        None
        """

    def commit(self) -> None:
        """Count the commit.

        Returns
        -------
        None
        """
        self.commits += 1


def make_user(
    email: str = TEST_EMAIL,
    password: str | None = VALID_PASSWORD,
    is_active: bool = True,
) -> User:
    """Build a user whose hash matches ``FakePasswordHasher``.

    Parameters
    ----------
    email : str
        E-mail of the user.
    password : str | None
        Password, or ``None`` for an SSO-only account.
    is_active : bool
        Whether the account is active.

    Returns
    -------
    User
        A new user.
    """
    return User(
        id=uuid4(),
        email=email,
        full_name="Camila Torres",
        job_title="Instructional designer",
        password_hash=f"hashed:{password}" if password is not None else None,
        is_active=is_active,
        last_login_at=None,
    )


def make_membership() -> OrganizationMembership:
    """Build an organization membership.

    Returns
    -------
    OrganizationMembership
        Membership with the ``author`` and ``reviewer`` roles.
    """
    return OrganizationMembership(
        organization_id=uuid4(),
        organization_name="Universidade Exemplo",
        organization_slug="universidade-exemplo",
        roles=("author", "reviewer"),
    )
