"""Tests of the PostgreSQL adapters against a recording fake connection.

They check SQL targets, parameters and row mapping; behavior against a
real database is out of the scope of the unit tests.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from coursegen_backend.application.ports.repositories import AuditEvent
from coursegen_backend.infrastructure.database import unit_of_work
from coursegen_backend.infrastructure.database.audit_log_repository import (
    PostgresAuditLogRepository,
)
from coursegen_backend.infrastructure.database.password_reset_token_repository import (
    PostgresPasswordResetTokenRepository,
)
from coursegen_backend.infrastructure.database.session_repository import (
    PostgresSessionRepository,
)
from coursegen_backend.infrastructure.database.user_repository import (
    PostgresUserRepository,
)

MOMENT = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


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


def test_user_repository_maps_rows_and_memberships() -> None:
    """Users and memberships are mapped from rows."""
    user_id = uuid4()
    connection = RecordingConnection(
        rows=[
            {
                "id": user_id,
                "email": "camila@uni.edu",
                "full_name": "Camila Torres",
                "job_title": None,
                "password_hash": "$argon2id$...",
                "is_active": True,
                "last_login_at": None,
            }
        ]
    )
    repository = PostgresUserRepository(connection)
    user = repository.get_by_email("Camila@Uni.edu")
    assert user.id == user_id
    assert "FROM coursegen.users WHERE email = %s" in connection.calls[0][0]
    membership_connection = RecordingConnection(
        rows=[
            {
                "id": uuid4(),
                "name": "Universidade",
                "slug": "uni",
                "roles": ["admin", "author"],
            }
        ]
    )
    memberships = PostgresUserRepository(
        membership_connection
    ).list_memberships(user_id)
    assert memberships[0].roles == ("admin", "author")


def test_user_repository_returns_none_when_missing() -> None:
    """Missing users map to ``None``."""
    assert PostgresUserRepository(RecordingConnection()).get_by_id(
        uuid4()
    ) is None


def test_session_repository_casts_ip_and_counts_revocations() -> None:
    """Sessions cast the IP to ``inet`` and report revoked rows."""
    session_row = {
        "id": uuid4(),
        "user_id": uuid4(),
        "keep_signed_in": True,
        "created_at": MOMENT,
        "expires_at": MOMENT,
        "revoked_at": None,
    }
    connection = RecordingConnection(rows=[session_row], rowcount=2)
    repository = PostgresSessionRepository(connection)
    session = repository.create(
        user_id=session_row["user_id"],
        refresh_token_hash="hash",
        keep_signed_in=True,
        user_agent="pytest",
        ip_address="203.0.113.7",
        expires_at=MOMENT,
    )
    assert session.id == session_row["id"]
    assert "%s::inet" in connection.calls[0][0]
    assert repository.revoke_all_for_user(session.user_id, MOMENT) == 2
    repository.get_by_refresh_token_hash("hash")
    assert "FOR UPDATE" in connection.calls[-1][0]


def test_reset_token_repository_maps_rows() -> None:
    """Reset tokens are mapped and invalidated per user."""
    token_row = {
        "id": uuid4(),
        "user_id": uuid4(),
        "expires_at": MOMENT,
        "used_at": None,
    }
    connection = RecordingConnection(rows=[token_row])
    repository = PostgresPasswordResetTokenRepository(connection)
    assert repository.get_by_token_hash("hash").id == token_row["id"]
    repository.invalidate_all_for_user(token_row["user_id"], MOMENT)
    assert "used_at IS NULL" in connection.calls[-1][0]


def test_audit_log_repository_records_and_counts() -> None:
    """Events are inserted as JSONB and counted per entity."""
    connection = RecordingConnection(rows=[{"total": 4}])
    repository = PostgresAuditLogRepository(connection)
    repository.record(AuditEvent(action="auth.login", details={"a": 1}))
    assert "INSERT INTO coursegen.audit_log" in connection.calls[0][0]
    assert (
        repository.count_for_entity_since(
            "auth.login_failed",
            "user",
            uuid4(),
            MOMENT,
        )
        == 4
    )


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
