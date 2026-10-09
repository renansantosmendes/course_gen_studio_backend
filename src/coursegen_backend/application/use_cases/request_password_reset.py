"""Use case: send a password recovery link by e-mail."""

import logging
import math

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import RequestContext
from coursegen_backend.application.policies import PasswordResetPolicy
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.email import (
    EmailDeliveryError,
    EmailSender,
)
from coursegen_backend.application.ports.repositories import AuditEvent
from coursegen_backend.application.ports.security import (
    OpaqueTokenGenerator,
)
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.application.services.password_reset_email import (
    build_password_reset_email,
)

logger = logging.getLogger(__name__)


class RequestPasswordResetUseCase:
    """Creates a single-use reset token and e-mails its link."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        token_generator: OpaqueTokenGenerator,
        email_sender: EmailSender,
        reset_policy: PasswordResetPolicy,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        token_generator : OpaqueTokenGenerator
            Creates and hashes the reset token.
        email_sender : EmailSender
            Delivers the recovery e-mail.
        reset_policy : PasswordResetPolicy
            Token lifetime and reset page address.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._token_generator = token_generator
        self._email_sender = email_sender
        self._reset_policy = reset_policy
        self._clock = clock

    def execute(
        self,
        email: str,
        context: RequestContext,
    ) -> None:
        """Send recovery instructions when the account exists.

        The call never reveals whether the e-mail is registered: it
        returns normally in every case, and delivery failures are only
        logged.

        Parameters
        ----------
        email : str
            Institutional e-mail informed by the user.
        context : RequestContext
            Information about the client.

        Returns
        -------
        None
        """
        moment = self._clock.now()
        with self._unit_of_work as uow:
            user = uow.users.get_by_email(email)
            if user is None or not user.can_sign_in_with_password:
                return
            token = self._token_generator.generate()
            uow.password_reset_tokens.create(
                user_id=user.id,
                token_hash=self._token_generator.hash(token),
                expires_at=moment + self._reset_policy.token_ttl,
            )
            uow.audit_log.record(
                AuditEvent(
                    action=audit_actions.PASSWORD_RESET_REQUESTED,
                    actor_user_id=user.id,
                    entity_type=audit_actions.USER_ENTITY,
                    entity_id=user.id,
                    ip_address=context.ip_address,
                )
            )
            uow.commit()
        message = build_password_reset_email(
            recipient=user.email,
            full_name=user.full_name,
            reset_link=self._reset_policy.build_reset_link(token),
            validity_minutes=math.ceil(
                self._reset_policy.token_ttl.total_seconds() / 60
            ),
        )
        try:
            self._email_sender.send(message)
        except EmailDeliveryError:
            logger.exception(
                "Could not deliver the password reset e-mail of user %s.",
                user.id,
            )
