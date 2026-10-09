"""PostgreSQL implementation of the password reset token repository."""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from coursegen_backend.application.ports.repositories import (
    PasswordResetTokenRepository,
)
from coursegen_backend.domain.entities import PasswordResetToken

TOKEN_COLUMNS = "id, user_id, expires_at, used_at"


def map_password_reset_token(row: dict[str, Any]) -> PasswordResetToken:
    """Convert a row of ``coursegen.password_reset_tokens`` to an entity.

    Parameters
    ----------
    row : dict[str, Any]
        Row with the columns listed in ``TOKEN_COLUMNS``.

    Returns
    -------
    PasswordResetToken
        The corresponding token.
    """
    return PasswordResetToken(
        id=row["id"],
        user_id=row["user_id"],
        expires_at=row["expires_at"],
        used_at=row["used_at"],
    )


class PostgresPasswordResetTokenRepository(PasswordResetTokenRepository):
    """Reads and updates ``coursegen.password_reset_tokens``."""

    def __init__(
        self,
        connection: Connection,
    ) -> None:
        """Create the repository.

        Parameters
        ----------
        connection : Connection
            Open connection whose transaction is managed by the unit of
            work.

        Returns
        -------
        None
        """
        self._connection = connection

    def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Insert a new reset token.

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
        row = self._connection.execute(
            f"""
            INSERT INTO coursegen.password_reset_tokens
                   (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            RETURNING {TOKEN_COLUMNS}
            """,
            (user_id, token_hash, expires_at),
        ).fetchone()
        return map_password_reset_token(row)

    def get_by_token_hash(
        self,
        token_hash: str,
    ) -> PasswordResetToken | None:
        """Find a reset token by its hash, locking its row.

        Parameters
        ----------
        token_hash : str
            Hash of the token.

        Returns
        -------
        PasswordResetToken | None
            The token, or ``None`` when it does not exist.
        """
        row = self._connection.execute(
            f"""
            SELECT {TOKEN_COLUMNS}
              FROM coursegen.password_reset_tokens
             WHERE token_hash = %s
               FOR UPDATE
            """,
            (token_hash,),
        ).fetchone()
        return map_password_reset_token(row) if row else None

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
        self._connection.execute(
            """
            UPDATE coursegen.password_reset_tokens
               SET used_at = %s
             WHERE user_id = %s AND used_at IS NULL
            """,
            (moment, user_id),
        )
