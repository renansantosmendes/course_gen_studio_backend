"""Use case: define a new password with a recovery token."""

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import RequestContext
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.repositories import AuditEvent
from coursegen_backend.application.ports.security import (
    OpaqueTokenGenerator,
    PasswordHasher,
)
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.exceptions import (
    InvalidPasswordResetTokenError,
    PasswordReuseError,
)
from coursegen_backend.domain.password_policy import PasswordPolicy


class ResetPasswordUseCase:
    """Redeems a reset token, replacing the password of its user."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        token_generator: OpaqueTokenGenerator,
        password_hasher: PasswordHasher,
        password_policy: PasswordPolicy,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        token_generator : OpaqueTokenGenerator
            Hashes the informed reset token.
        password_hasher : PasswordHasher
            Hashes the new password.
        password_policy : PasswordPolicy
            Strength rules of the new password.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._token_generator = token_generator
        self._password_hasher = password_hasher
        self._password_policy = password_policy
        self._clock = clock

    def execute(
        self,
        reset_token: str,
        new_password: str,
        context: RequestContext,
    ) -> None:
        """Replace the password and end every session of the user.

        Every pending reset token of the user is invalidated as well.

        Parameters
        ----------
        reset_token : str
            Token received in the recovery e-mail.
        new_password : str
            New password in plain text.
        context : RequestContext
            Information about the client.

        Returns
        -------
        None

        Raises
        ------
        InvalidPasswordResetTokenError
            When the token is unknown, expired or already used, or the
            account was deactivated.
        WeakPasswordError
            When the new password breaks the password policy.
        PasswordReuseError
            When the new password equals the current one.
        """
        moment = self._clock.now()
        with self._unit_of_work as uow:
            token = uow.password_reset_tokens.get_by_token_hash(
                self._token_generator.hash(reset_token)
            )
            if token is None or not token.is_usable(moment):
                raise InvalidPasswordResetTokenError()
            user = uow.users.get_by_id(token.user_id)
            if user is None or not user.is_active:
                raise InvalidPasswordResetTokenError()
            self._password_policy.validate(new_password, user.email)
            if user.password_hash is not None and self._password_hasher.verify(
                user.password_hash,
                new_password,
            ):
                raise PasswordReuseError()
            uow.users.update_password_hash(
                user.id,
                self._password_hasher.hash(new_password),
            )
            uow.password_reset_tokens.invalidate_all_for_user(user.id, moment)
            revoked_sessions = uow.sessions.revoke_all_for_user(
                user.id,
                moment,
            )
            uow.audit_log.record(
                AuditEvent(
                    action=audit_actions.PASSWORD_RESET_COMPLETED,
                    actor_user_id=user.id,
                    entity_type=audit_actions.USER_ENTITY,
                    entity_id=user.id,
                    details={"revoked_sessions": revoked_sessions},
                    ip_address=context.ip_address,
                )
            )
            uow.commit()
