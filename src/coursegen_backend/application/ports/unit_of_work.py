"""Port that groups repositories in a single atomic transaction."""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from coursegen_backend.application.ports.repositories import (
    AuditLogRepository,
    PasswordResetTokenRepository,
    SessionRepository,
    UserRepository,
)


class UnitOfWork(ABC):
    """Transaction boundary shared by the repositories of a use case.

    Changes are persisted only when :meth:`commit` is called inside the
    ``with`` block; leaving the block without committing discards them.

    Attributes
    ----------
    users : UserRepository
        Access to user accounts.
    sessions : SessionRepository
        Access to signed-in sessions.
    password_reset_tokens : PasswordResetTokenRepository
        Access to password reset tokens.
    audit_log : AuditLogRepository
        Access to the audit trail.

    Example
    -------
    >>> with unit_of_work as uow:
    ...     uow.users.update_last_login(user_id, now)
    ...     uow.commit()
    """

    users: UserRepository
    sessions: SessionRepository
    password_reset_tokens: PasswordResetTokenRepository
    audit_log: AuditLogRepository

    @abstractmethod
    def __enter__(self) -> Self:
        """Begin the transaction.

        Returns
        -------
        Self
            The unit of work, with repositories ready to use.
        """

    @abstractmethod
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """End the transaction, discarding uncommitted changes.

        Parameters
        ----------
        exception_type : type[BaseException] | None
            Type of the exception raised inside the block, if any.
        exception : BaseException | None
            Exception raised inside the block, if any.
        traceback : TracebackType | None
            Traceback of the exception, if any.

        Returns
        -------
        None
        """

    @abstractmethod
    def commit(self) -> None:
        """Persist every change made so far in the transaction.

        Returns
        -------
        None
        """
