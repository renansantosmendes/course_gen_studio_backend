"""Tests of the PostgreSQL adapters against a recording fake connection.

They check SQL targets, parameters and row mapping; behavior against a
real database is out of the scope of the unit tests.
"""

from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from psycopg import errors

from coursegen_backend.domain.exceptions import AccountLinkConflictError
from coursegen_backend.infrastructure.database import unit_of_work
from coursegen_backend.infrastructure.database.user_repository import (
    PostgresUserRepository,
)
from tests.fakes import make_identity


class RecordingConnection:
    """Fake psycopg connection that returns canned rows."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        rowcount: int = 0,
    ) -> None:
        """Create the connection.

        Parameters
        ----------
        rows : list[dict[str, Any]] | None
            Rows returned by every query.
        rowcount : int
            Value of ``cursor.rowcount``.

        Returns
        -------
        None
        """
        self.rows = rows or []
        self.rowcount = rowcount
        self.calls = []

    def execute(
        self,
        query: str,
        parameters: tuple,
    ) -> MagicMock:
        """Record the query and return a cursor over the canned rows.

        Parameters
        ----------
        query : str
            SQL text.
        parameters : tuple
            Query parameters.

        Returns
        -------
        MagicMock
            Cursor with ``fetchone``, ``fetchall`` and ``rowcount``.
        """
        self.calls.append((" ".join(query.split()), parameters))
        cursor = MagicMock()
        cursor.fetchone.return_value = self.rows[0] if self.rows else None
        cursor.fetchall.return_value = self.rows
        cursor.rowcount = self.rowcount
        return cursor


def user_row(user_id: UUID) -> dict[str, Any]:
    """Build a row of ``coursegen.users``.

    Parameters
    ----------
    user_id : UUID
        Identifier of the user.

    Returns
    -------
    dict[str, Any]
        Row with every selected column.
    """
    return {
        "id": user_id,
        "email": "camila@example.com",
        "full_name": "Camila Torres",
        "job_title": None,
        "is_active": True,
    }


def test_get_by_id_maps_row() -> None:
    """Profiles are read from ``coursegen.users``."""
    user_id = uuid4()
    connection = RecordingConnection(rows=[user_row(user_id)])
    user = PostgresUserRepository(connection).get_by_id(user_id)
    assert user.id == user_id
    assert "FROM coursegen.users WHERE id = %s" in connection.calls[0][0]


def test_get_by_id_returns_none_when_missing() -> None:
    """Unknown identifiers map to ``None``."""
    assert PostgresUserRepository(RecordingConnection()).get_by_id(
        uuid4()
    ) is None


def test_save_identity_upserts_only_identity_fields() -> None:
    """The upsert touches e-mail and name, never local fields."""
    identity = make_identity()
    connection = RecordingConnection(rows=[user_row(identity.user_id)])
    PostgresUserRepository(connection).save_identity(identity)
    query, parameters = connection.calls[0]
    assert "ON CONFLICT (id) DO UPDATE" in query
    assert "job_title" not in query.split("DO UPDATE")[1].split("RETURNING")[0]
    assert "is_active =" not in query
    assert parameters == (identity.user_id, identity.email, identity.full_name)


def test_save_identity_translates_email_conflict() -> None:
    """A unique violation on e-mail becomes a link conflict."""
    connection = MagicMock()
    connection.execute.side_effect = errors.UniqueViolation("duplicate")
    with pytest.raises(AccountLinkConflictError):
        PostgresUserRepository(connection).save_identity(make_identity())


def test_list_memberships_maps_roles() -> None:
    """Memberships group the roles of each organization."""
    connection = RecordingConnection(
        rows=[
            {
                "id": uuid4(),
                "name": "Universidade",
                "slug": "uni",
                "roles": ["admin", "author"],
            }
        ]
    )
    memberships = PostgresUserRepository(connection).list_memberships(uuid4())
    assert memberships[0].roles == ("admin", "author")


def test_unit_of_work_rolls_back_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leaving the block always rolls back pending work and closes.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Replaces ``psycopg.connect``.

    Returns
    -------
    None
    """
    connection = MagicMock()
    monkeypatch.setattr(
        unit_of_work.psycopg,
        "connect",
        MagicMock(return_value=connection),
    )
    work = unit_of_work.PostgresUnitOfWork("postgresql://db/test")
    with work as uow:
        assert isinstance(uow.users, PostgresUserRepository)
        uow.commit()
    connection.commit.assert_called_once()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
