"""PostgreSQL implementation of the audit trail."""

from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from coursegen_backend.application.ports.repositories import (
    AuditEvent,
    AuditLogRepository,
)


class PostgresAuditLogRepository(AuditLogRepository):
    """Appends to and counts entries of ``coursegen.audit_log``."""

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

    def record(
        self,
        event: AuditEvent,
    ) -> None:
        """Insert an event into the audit trail.

        Parameters
        ----------
        event : AuditEvent
            Event to record.

        Returns
        -------
        None
        """
        self._connection.execute(
            """
            INSERT INTO coursegen.audit_log
                   (actor_user_id, action, entity_type, entity_id,
                    details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s::inet)
            """,
            (
                event.actor_user_id,
                event.action,
                event.entity_type,
                event.entity_id,
                Jsonb(event.details),
                event.ip_address,
            ),
        )

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
            Action to count.
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
        row = self._connection.execute(
            """
            SELECT count(*) AS total
              FROM coursegen.audit_log
             WHERE entity_type = %s
               AND entity_id = %s
               AND action = %s
               AND created_at >= %s
            """,
            (entity_type, entity_id, action, since),
        ).fetchone()
        return row["total"]
