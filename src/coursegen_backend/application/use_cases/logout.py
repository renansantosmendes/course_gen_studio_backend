"""Use case: end the current session."""

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    RequestContext,
)
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.repositories import AuditEvent
from coursegen_backend.application.ports.unit_of_work import UnitOfWork


class LogoutUseCase:
    """Revokes the session of the authenticated user."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._clock = clock

    def execute(
        self,
        principal: AuthenticatedPrincipal,
        context: RequestContext,
    ) -> None:
        """End the session, invalidating its access and refresh tokens.

        Parameters
        ----------
        principal : AuthenticatedPrincipal
            The authenticated user and session.
        context : RequestContext
            Information about the client.

        Returns
        -------
        None
        """
        with self._unit_of_work as uow:
            uow.sessions.revoke(principal.session_id, self._clock.now())
            uow.audit_log.record(
                AuditEvent(
                    action=audit_actions.LOGOUT,
                    actor_user_id=principal.user.id,
                    entity_type=audit_actions.SESSION_ENTITY,
                    entity_id=principal.session_id,
                    ip_address=context.ip_address,
                )
            )
            uow.commit()
