"""PostgreSQL implementation of the user repository."""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from coursegen_backend.application.ports.repositories import UserRepository
from coursegen_backend.domain.entities import OrganizationMembership, User

USER_COLUMNS = """
    id, email, full_name, job_title, password_hash, is_active,
    last_login_at
"""


def map_user(row: dict[str, Any]) -> User:
    """Convert a row of ``coursegen.users`` into a domain entity.

    Parameters
    ----------
    row : dict[str, Any]
        Row with the columns listed in ``USER_COLUMNS``.

    Returns
    -------
    User
        The corresponding user.
    """
    return User(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        job_title=row["job_title"],
        password_hash=row["password_hash"],
        is_active=row["is_active"],
        last_login_at=row["last_login_at"],
    )


class PostgresUserRepository(UserRepository):
    """Reads and updates ``coursegen.users``."""

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

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        """Find a user by e-mail; the ``citext`` column ignores case.

        Parameters
        ----------
        email : str
            E-mail address.

        Returns
        -------
        User | None
            The user, or ``None`` when no account uses the e-mail.
        """
        row = self._connection.execute(
            f"SELECT {USER_COLUMNS} FROM coursegen.users WHERE email = %s",
            (email,),
        ).fetchone()
        return map_user(row) if row else None

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
        row = self._connection.execute(
            f"SELECT {USER_COLUMNS} FROM coursegen.users WHERE id = %s",
            (user_id,),
        ).fetchone()
        return map_user(row) if row else None

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
        self._connection.execute(
            "UPDATE coursegen.users SET password_hash = %s WHERE id = %s",
            (password_hash, user_id),
        )

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
        self._connection.execute(
            "UPDATE coursegen.users SET last_login_at = %s WHERE id = %s",
            (moment, user_id),
        )

    def list_memberships(
        self,
        user_id: UUID,
    ) -> list[OrganizationMembership]:
        """List the organizations of a user with the roles held in each.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        list[OrganizationMembership]
            Memberships ordered by organization name.
        """
        rows = self._connection.execute(
            """
            SELECT o.id, o.name, o.slug,
                   array_agg(m.role ORDER BY m.role) AS roles
              FROM coursegen.organization_members m
              JOIN coursegen.organizations o ON o.id = m.organization_id
             WHERE m.user_id = %s
             GROUP BY o.id, o.name, o.slug
             ORDER BY o.name
            """,
            (user_id,),
        ).fetchall()
        return [
            OrganizationMembership(
                organization_id=row["id"],
                organization_name=row["name"],
                organization_slug=row["slug"],
                roles=tuple(row["roles"]),
            )
            for row in rows
        ]
