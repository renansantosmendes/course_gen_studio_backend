"""PostgreSQL implementation of the user repository."""

from typing import Any
from uuid import UUID

from psycopg import Connection, errors

from coursegen_backend.application.ports.repositories import UserRepository
from coursegen_backend.domain.entities import (
    OrganizationMembership,
    User,
    VerifiedIdentity,
)
from coursegen_backend.domain.exceptions import AccountLinkConflictError

USER_COLUMNS = "id, email, full_name, job_title, is_active"


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
        is_active=row["is_active"],
    )


class PostgresUserRepository(UserRepository):
    """Reads and provisions ``coursegen.users``."""

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

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        """Find a profile by identifier.

        Parameters
        ----------
        user_id : UUID
            Identifier shared with the auth service.

        Returns
        -------
        User | None
            The profile, or ``None`` when it does not exist yet.
        """
        row = self._connection.execute(
            f"SELECT {USER_COLUMNS} FROM coursegen.users WHERE id = %s",
            (user_id,),
        ).fetchone()
        return map_user(row) if row else None

    def save_identity(
        self,
        identity: VerifiedIdentity,
    ) -> User:
        """Insert the profile of an identity, or refresh its e-mail and name.

        ``job_title`` and ``is_active`` belong to CourseGen and are never
        overwritten.

        Parameters
        ----------
        identity : VerifiedIdentity
            Identity read from a valid access token.

        Returns
        -------
        User
            The stored profile.

        Raises
        ------
        AccountLinkConflictError
            When another profile already uses the identity's e-mail.
        """
        try:
            row = self._connection.execute(
                f"""
                INSERT INTO coursegen.users (id, email, full_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                   SET email = EXCLUDED.email,
                       full_name = EXCLUDED.full_name
                RETURNING {USER_COLUMNS}
                """,
                (identity.user_id, identity.email, identity.full_name),
            ).fetchone()
        except errors.UniqueViolation as error:
            raise AccountLinkConflictError() from error
        return map_user(row)

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
