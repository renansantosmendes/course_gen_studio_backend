"""Use case: sign in with e-mail and password."""

import math
from dataclasses import replace
from datetime import datetime

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import (
    LoginResult,
    RequestContext,
    UserProfile,
)
from coursegen_backend.application.policies import LoginThrottlePolicy
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.repositories import AuditEvent
from coursegen_backend.application.ports.security import PasswordHasher
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.domain.entities import User
from coursegen_backend.domain.exceptions import (
    InvalidCredentialsError,
    TooManyLoginAttemptsError,
)


class LoginUseCase:
    """Authenticates a user and opens a new session."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        password_hasher: PasswordHasher,
        session_token_issuer: SessionTokenIssuer,
        throttle_policy: LoginThrottlePolicy,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        password_hasher : PasswordHasher
            Verifies the informed password.
        session_token_issuer : SessionTokenIssuer
            Opens the session and issues its tokens.
        throttle_policy : LoginThrottlePolicy
            Limits on failed attempts per account.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._password_hasher = password_hasher
        self._session_token_issuer = session_token_issuer
        self._throttle_policy = throttle_policy
        self._clock = clock

    def execute(
        self,
        email: str,
        password: str,
        keep_signed_in: bool,
        context: RequestContext,
    ) -> LoginResult:
        """Sign the user in.

        Failed attempts are recorded in the audit trail. After too many
        failures inside the throttle window, the account is temporarily
        blocked, even for the correct password.

        Parameters
        ----------
        email : str
            Institutional e-mail of the account.
        password : str
            Password in plain text.
        keep_signed_in : bool
            Whether the session should use the long lifetime.
        context : RequestContext
            Information about the client.

        Returns
        -------
        LoginResult
            Session credentials and the user profile.

        Raises
        ------
        InvalidCredentialsError
            When the e-mail is unknown, the account is inactive or has
            no password, or the password is wrong.
        TooManyLoginAttemptsError
            When the account is temporarily blocked.

        Example
        -------
        >>> result = login_use_case.execute(
        ...     email="ana@example.com",
        ...     password=password_typed_by_user,
        ...     keep_signed_in=True,
        ...     context=RequestContext(ip_address="203.0.113.7"),
        ... )
        >>> result.tokens.access_token
        '<access-token>'
        """
        moment = self._clock.now()
        with self._unit_of_work as uow:
            user = uow.users.get_by_email(email)
            if user is not None:
                self._ensure_not_throttled(uow, user, moment)
            if not self._password_matches(user, password):
                uow.audit_log.record(
                    AuditEvent(
                        action=audit_actions.LOGIN_FAILED,
                        entity_type=audit_actions.USER_ENTITY
                        if user
                        else None,
                        entity_id=user.id if user else None,
                        details={"email": email},
                        ip_address=context.ip_address,
                    )
                )
                uow.commit()
                raise InvalidCredentialsError()
            if self._password_hasher.needs_rehash(user.password_hash):
                uow.users.update_password_hash(
                    user.id,
                    self._password_hasher.hash(password),
                )
            uow.users.update_last_login(user.id, moment)
            user = replace(user, last_login_at=moment)
            tokens = self._session_token_issuer.open_session(
                unit_of_work=uow,
                user=user,
                keep_signed_in=keep_signed_in,
                context=context,
                moment=moment,
            )
            memberships = uow.users.list_memberships(user.id)
            uow.audit_log.record(
                AuditEvent(
                    action=audit_actions.LOGIN_SUCCEEDED,
                    actor_user_id=user.id,
                    entity_type=audit_actions.SESSION_ENTITY,
                    entity_id=tokens.session_id,
                    details={"keep_signed_in": keep_signed_in},
                    ip_address=context.ip_address,
                )
            )
            uow.commit()
        return LoginResult(
            tokens=tokens,
            profile=UserProfile(user=user, memberships=memberships),
        )

    def _ensure_not_throttled(
        self,
        unit_of_work: UnitOfWork,
        user: User,
        moment: datetime,
    ) -> None:
        """Block the attempt when the account has too many failures.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Active transaction.
        user : User
            Account being accessed.
        moment : datetime
            Current moment, the end of the counting window.

        Returns
        -------
        None

        Raises
        ------
        TooManyLoginAttemptsError
            When the failure limit inside the window was reached.
        """
        window = self._throttle_policy.window
        failures = unit_of_work.audit_log.count_for_entity_since(
            action=audit_actions.LOGIN_FAILED,
            entity_type=audit_actions.USER_ENTITY,
            entity_id=user.id,
            since=moment - window,
        )
        if failures >= self._throttle_policy.max_failed_attempts:
            raise TooManyLoginAttemptsError(
                retry_after_seconds=math.ceil(window.total_seconds())
            )

    def _password_matches(
        self,
        user: User | None,
        password: str,
    ) -> bool:
        """Check the password, spending similar time for unknown users.

        Parameters
        ----------
        user : User | None
            Account found for the e-mail, if any.
        password : str
            Password in plain text.

        Returns
        -------
        bool
            ``True`` when the account can sign in with this password.
        """
        if user is None or not user.can_sign_in_with_password:
            self._password_hasher.simulate_verification(password)
            return False
        return self._password_hasher.verify(user.password_hash, password)
