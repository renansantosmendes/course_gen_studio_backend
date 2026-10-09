"""Creates and renews the credentials of signed-in sessions."""

from datetime import datetime

from coursegen_backend.application.dto import RequestContext, SessionTokens
from coursegen_backend.application.policies import SessionPolicy
from coursegen_backend.application.ports.security import (
    AccessTokenService,
    OpaqueTokenGenerator,
)
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.entities import User, UserSession


class SessionTokenIssuer:
    """Opens sessions and rotates their refresh tokens."""

    def __init__(
        self,
        access_token_service: AccessTokenService,
        token_generator: OpaqueTokenGenerator,
        session_policy: SessionPolicy,
    ) -> None:
        """Create the issuer.

        Parameters
        ----------
        access_token_service : AccessTokenService
            Issues the access tokens.
        token_generator : OpaqueTokenGenerator
            Creates and hashes refresh tokens.
        session_policy : SessionPolicy
            Lifetimes of refresh tokens.

        Returns
        -------
        None
        """
        self._access_token_service = access_token_service
        self._token_generator = token_generator
        self._session_policy = session_policy

    def open_session(
        self,
        unit_of_work: UnitOfWork,
        user: User,
        keep_signed_in: bool,
        context: RequestContext,
        moment: datetime,
    ) -> SessionTokens:
        """Store a new session and issue its tokens.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Active transaction in which the session is stored.
        user : User
            Owner of the session.
        keep_signed_in : bool
            Whether the session uses the long lifetime.
        context : RequestContext
            Client information recorded with the session.
        moment : datetime
            Current moment.

        Returns
        -------
        SessionTokens
            Credentials of the new session.
        """
        refresh_token = self._token_generator.generate()
        session = unit_of_work.sessions.create(
            user_id=user.id,
            refresh_token_hash=self._token_generator.hash(refresh_token),
            keep_signed_in=keep_signed_in,
            user_agent=context.user_agent,
            ip_address=context.ip_address,
            expires_at=moment
            + self._session_policy.refresh_token_ttl_for(keep_signed_in),
        )
        return self._build_tokens(session, refresh_token, moment)

    def rotate_session(
        self,
        unit_of_work: UnitOfWork,
        session: UserSession,
        moment: datetime,
    ) -> SessionTokens:
        """Replace the refresh token of a session and issue new tokens.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Active transaction in which the session is updated.
        session : UserSession
            Session being renewed.
        moment : datetime
            Current moment.

        Returns
        -------
        SessionTokens
            New credentials of the session.
        """
        refresh_token = self._token_generator.generate()
        rotated_session = unit_of_work.sessions.rotate_refresh_token(
            session_id=session.id,
            refresh_token_hash=self._token_generator.hash(refresh_token),
            expires_at=moment
            + self._session_policy.refresh_token_ttl_for(
                session.keep_signed_in
            ),
        )
        return self._build_tokens(rotated_session, refresh_token, moment)

    def _build_tokens(
        self,
        session: UserSession,
        refresh_token: str,
        moment: datetime,
    ) -> SessionTokens:
        """Combine a session and its refresh token with an access token.

        Parameters
        ----------
        session : UserSession
            Stored session.
        refresh_token : str
            Refresh token in plain text.
        moment : datetime
            Current moment, used as the access token issue time.

        Returns
        -------
        SessionTokens
            Credentials of the session.
        """
        access_token = self._access_token_service.issue(
            user_id=session.user_id,
            session_id=session.id,
            issued_at=moment,
        )
        return SessionTokens(
            session_id=session.id,
            access_token=access_token.token,
            access_token_expires_at=access_token.expires_at,
            refresh_token=refresh_token,
            refresh_token_expires_at=session.expires_at,
        )
