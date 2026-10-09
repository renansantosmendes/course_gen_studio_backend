"""Use case: exchange a refresh token for new session credentials."""

from coursegen_backend.application.dto import SessionTokens
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.security import (
    OpaqueTokenGenerator,
)
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.domain.exceptions import InvalidRefreshTokenError


class RefreshSessionUseCase:
    """Renews a session, rotating its refresh token."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        token_generator: OpaqueTokenGenerator,
        session_token_issuer: SessionTokenIssuer,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        token_generator : OpaqueTokenGenerator
            Hashes the informed refresh token.
        session_token_issuer : SessionTokenIssuer
            Rotates the session credentials.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._token_generator = token_generator
        self._session_token_issuer = session_token_issuer
        self._clock = clock

    def execute(
        self,
        refresh_token: str,
    ) -> SessionTokens:
        """Issue new credentials for the session of a refresh token.

        The informed refresh token stops working: the client must keep
        the new one returned by this call.

        Parameters
        ----------
        refresh_token : str
            Refresh token received at sign-in or at the last refresh.

        Returns
        -------
        SessionTokens
            New credentials of the same session.

        Raises
        ------
        InvalidRefreshTokenError
            When the token is unknown, the session ended or expired, or
            the account was deactivated.
        """
        moment = self._clock.now()
        with self._unit_of_work as uow:
            session = uow.sessions.get_by_refresh_token_hash(
                self._token_generator.hash(refresh_token)
            )
            if session is None or not session.is_active(moment):
                raise InvalidRefreshTokenError()
            user = uow.users.get_by_id(session.user_id)
            if user is None or not user.is_active:
                uow.sessions.revoke(session.id, moment)
                uow.commit()
                raise InvalidRefreshTokenError()
            tokens = self._session_token_issuer.rotate_session(
                unit_of_work=uow,
                session=session,
                moment=moment,
            )
            uow.commit()
        return tokens
