"""Use case: identify the user behind an access token."""

from coursegen_backend.application.dto import AuthenticatedPrincipal
from coursegen_backend.application.ports.clock import Clock
from coursegen_backend.application.ports.security import AccessTokenService
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.exceptions import InvalidAccessTokenError


class AuthenticateUseCase:
    """Validates access tokens against the stored sessions."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        access_token_service: AccessTokenService,
        clock: Clock,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        access_token_service : AccessTokenService
            Validates and decodes the access token.
        clock : Clock
            Source of the current time.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._access_token_service = access_token_service
        self._clock = clock

    def execute(
        self,
        access_token: str,
    ) -> AuthenticatedPrincipal:
        """Resolve the user and session of an access token.

        Besides the token signature and expiration, the session must
        still be open and the account active, so signing out or
        resetting the password takes effect immediately.

        Parameters
        ----------
        access_token : str
            Encoded access token.

        Returns
        -------
        AuthenticatedPrincipal
            The authenticated user and session.

        Raises
        ------
        InvalidAccessTokenError
            When the token is invalid, the session ended or the account
            is inactive.
        """
        claims = self._access_token_service.decode(access_token)
        moment = self._clock.now()
        with self._unit_of_work as uow:
            session = uow.sessions.get_by_id(claims.session_id)
            if (
                session is None
                or session.user_id != claims.user_id
                or not session.is_active(moment)
            ):
                raise InvalidAccessTokenError()
            user = uow.users.get_by_id(claims.user_id)
            if user is None or not user.is_active:
                raise InvalidAccessTokenError()
        return AuthenticatedPrincipal(user=user, session_id=session.id)
