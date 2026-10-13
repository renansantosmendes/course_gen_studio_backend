"""Use case: identify the CourseGen user behind an access token."""

from coursegen_backend.application.dto import AuthenticatedPrincipal
from coursegen_backend.application.ports.security import AccessTokenVerifier
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.exceptions import AccountDisabledError


class AuthenticateUseCase:
    """Trusts tokens from the auth service and provisions local profiles."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        access_token_verifier: AccessTokenVerifier,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.
        access_token_verifier : AccessTokenVerifier
            Validates tokens issued by the auth service.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work
        self._access_token_verifier = access_token_verifier

    def execute(
        self,
        access_token: str,
    ) -> AuthenticatedPrincipal:
        """Resolve the CourseGen user of an access token.

        The first time an account reaches CourseGen, its profile is
        created with the token's identifier, e-mail and name; later, the
        e-mail and name are refreshed when they change in the auth
        service. Nothing is written when the profile is already current.

        Parameters
        ----------
        access_token : str
            Encoded access token issued by the auth service.

        Returns
        -------
        AuthenticatedPrincipal
            The authenticated CourseGen user.

        Raises
        ------
        InvalidAccessTokenError
            When the token is not valid.
        AccountDisabledError
            When the person was blocked from CourseGen Studio.
        AccountLinkConflictError
            When another profile already uses the account's e-mail.

        Example
        -------
        >>> principal = authenticate_use_case.execute(bearer_token)
        >>> principal.user.email
        'ana@example.com'
        """
        identity = self._access_token_verifier.verify(access_token)
        with self._unit_of_work as uow:
            user = uow.users.get_by_id(identity.user_id)
            if user is None or not user.matches(identity):
                user = uow.users.save_identity(identity)
                uow.commit()
        if not user.is_active:
            raise AccountDisabledError()
        return AuthenticatedPrincipal(user=user)
