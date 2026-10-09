"""Unit of work backed by a PostgreSQL transaction."""

from types import TracebackType
from typing import Self

import psycopg
from psycopg.rows import dict_row

from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.infrastructure.database import (
    password_reset_token_repository,
)
from coursegen_backend.infrastructure.database.audit_log_repository import (
    PostgresAuditLogRepository,
)
from coursegen_backend.infrastructure.database.session_repository import (
    PostgresSessionRepository,
)
from coursegen_backend.infrastructure.database.user_repository import (
    PostgresUserRepository,
)


class PostgresUnitOfWork(UnitOfWork):
    """Opens one connection per ``with`` block and one transaction in it.

    Designed for serverless runtimes such as Vercel: no connection is
    kept between requests. Use the pooled connection string of Neon
    (host ending in ``-pooler``) to keep connection setup cheap.
    """

    def __init__(
        self,
        database_url: str,
        connect_timeout_seconds: int = 10,
    ) -> None:
        """Create the unit of work without connecting yet.

        Parameters
        ----------
        database_url : str
            PostgreSQL connection string of the ``coursegen_app`` role.
        connect_timeout_seconds : int
            Maximum time to wait for a connection.

        Returns
        -------
        None
        """
        self._database_url = database_url
        self._connect_timeout_seconds = connect_timeout_seconds
        self._connection = None

    def __enter__(self) -> Self:
        """Connect and expose the repositories bound to the connection.

        Returns
        -------
        Self
            The unit of work, with repositories ready to use.
        """
        self._connection = psycopg.connect(
            self._database_url,
            row_factory=dict_row,
            connect_timeout=self._connect_timeout_seconds,
        )
        self.users = PostgresUserRepository(self._connection)
        self.sessions = PostgresSessionRepository(self._connection)
        self.password_reset_tokens = (
            password_reset_token_repository.PostgresPasswordResetTokenRepository(
                self._connection
            )
        )
        self.audit_log = PostgresAuditLogRepository(self._connection)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Discard uncommitted changes and close the connection.

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
        if self._connection is None:
            return
        try:
            self._connection.rollback()
        finally:
            self._connection.close()
            self._connection = None

    def commit(self) -> None:
        """Commit the current transaction.

        Returns
        -------
        None
        """
        self._connection.commit()
