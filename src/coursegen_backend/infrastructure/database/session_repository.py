"""PostgreSQL implementation of the session repository."""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from coursegen_backend.application.ports.repositories import (
    SessionRepository,
)
from coursegen_backend.domain.entities import UserSession

SESSION_COLUMNS = """
    id, user_id, keep_signed_in, created_at, expires_at, revoked_at
"""


def map_session(row: dict[str, Any]) -> UserSession:
    """Convert a row of ``coursegen.user_sessions`` into an entity.

    Parameters
    ----------
    row : dict[str, Any]
        Row with the columns listed in ``SESSION_COLUMNS``.

    Returns
    -------
    UserSession
        The corresponding session.
    """
    return UserSession(
        id=row["id"],
        user_id=row["user_id"],
        keep_signed_in=row["keep_signed_in"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
    )


class PostgresSessionRepository(SessionRepository):
    """Reads and updates ``coursegen.user_sessions``."""

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
        refresh_token_hash: str,
        keep_signed_in: bool,
        user_agent: str | None,
        ip_address: str | None,
        expires_at: datetime,
    ) -> UserSession:
        """Insert a new session.

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
            Validated IP address of the client.
        expires_at : datetime
            Expiration moment of the refresh token.

        Returns
        -------
        UserSession
            The stored session.
        """
        row = self._connection.execute(
            f"""
            INSERT INTO coursegen.user_sessions
                   (user_id, refresh_token_hash, keep_signed_in,
                    user_agent, ip_address, expires_at)
            VALUES (%s, %s, %s, %s, %s::inet, %s)
            RETURNING {SESSION_COLUMNS}
            """,
            (
                user_id,
                refresh_token_hash,
                keep_signed_in,
                user_agent,
                ip_address,
                expires_at,
            ),
        ).fetchone()
        return map_session(row)

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
        row = self._connection.execute(
            f"""
            SELECT {SESSION_COLUMNS}
              FROM coursegen.user_sessions
             WHERE id = %s
            """,
            (session_id,),
        ).fetchone()
        return map_session(row) if row else None

    def get_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> UserSession | None:
        """Find the session that owns a refresh token, locking its row.

        The row lock makes concurrent refreshes with the same token
        wait, so only one of them can rotate it.

        Parameters
        ----------
        refresh_token_hash : str
            Hash of the refresh token.

        Returns
        -------
        UserSession | None
            The session, or ``None`` when no session owns the token.
        """
        row = self._connection.execute(
            f"""
            SELECT {SESSION_COLUMNS}
              FROM coursegen.user_sessions
             WHERE refresh_token_hash = %s
               FOR UPDATE
            """,
            (refresh_token_hash,),
        ).fetchone()
        return map_session(row) if row else None

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
        row = self._connection.execute(
            f"""
            UPDATE coursegen.user_sessions
               SET refresh_token_hash = %s, expires_at = %s
             WHERE id = %s
            RETURNING {SESSION_COLUMNS}
            """,
            (refresh_token_hash, expires_at, session_id),
        ).fetchone()
        return map_session(row)

    def revoke(
        self,
        session_id: UUID,
        moment: datetime,
    ) -> None:
        """End a session, keeping the original moment if already ended.

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
        self._connection.execute(
            """
            UPDATE coursegen.user_sessions
               SET revoked_at = %s
             WHERE id = %s AND revoked_at IS NULL
            """,
            (moment, session_id),
        )

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
        cursor = self._connection.execute(
            """
            UPDATE coursegen.user_sessions
               SET revoked_at = %s
             WHERE user_id = %s
               AND revoked_at IS NULL
               AND expires_at > %s
               AND id IS DISTINCT FROM %s
            """,
            (moment, user_id, moment, except_session_id),
        )
        return cursor.rowcount
