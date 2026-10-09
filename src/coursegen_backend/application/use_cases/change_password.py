"""Use case: change the password of the authenticated user."""

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    RequestContext,
)
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.repositories import AuditEvent
from coursegen_backend.application.ports.security import PasswordHasher
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.exceptions import (
    IncorrectCurrentPasswordError,
    PasswordReuseError,
)
from coursegen_backend.domain.password_policy import PasswordPolicy


class ChangePasswordUseCase:
    """Replaces the password after confirming the current one."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        password_hasher: PasswordHasher,
        password_policy: PasswordPolicy,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        password_hasher : PasswordHasher
            Verifies the current password and hashes the new one.
        password_policy : PasswordPolicy
            Strength rules of the new password.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._password_hasher = password_hasher
        self._password_policy = password_policy
        self._clock = clock

    def execute(
        self,
        principal: AuthenticatedPrincipal,
        current_password: str,
        new_password: str,
        context: RequestContext,
    ) -> None:
        """Change the password and end the other sessions of the user.

        The session that made the request stays open.

        Parameters
        ----------
        principal : AuthenticatedPrincipal
            The authenticated user and session.
        current_password : str
            Current password in plain text.
        new_password : str
            New password in plain text.
        context : RequestContext
            Information about the client.

        Returns
        -------
        None

        Raises
        ------
        IncorrectCurrentPasswordError
            When the current password is wrong or the account has no
            password.
        WeakPasswordError
            When the new password breaks the password policy.
        PasswordReuseError
            When the new password equals the current one.
        """
        moment = self._clock.now()
        with self._unit_of_work as uow:
            user = uow.users.get_by_id(principal.user.id)
            if (
                user is None
                or user.password_hash is None
                or not self._password_hasher.verify(
                    user.password_hash,
                    current_password,
                )
            ):
                raise IncorrectCurrentPasswordError()
            self._password_policy.validate(new_password, user.email)
            if new_password == current_password:
                raise PasswordReuseError()
            uow.users.update_password_hash(
                user.id,
                self._password_hasher.hash(new_password),
            )
            uow.password_reset_tokens.invalidate_all_for_user(user.id, moment)
            revoked_sessions = uow.sessions.revoke_all_for_user(
                user.id,
                moment,
                except_session_id=principal.session_id,
            )
            uow.audit_log.record(
                AuditEvent(
                    action=audit_actions.PASSWORD_CHANGED,
                    actor_user_id=user.id,
                    entity_type=audit_actions.USER_ENTITY,
                    entity_id=user.id,
                    details={"revoked_sessions": revoked_sessions},
                    ip_address=context.ip_address,
                )
            )
            uow.commit()
