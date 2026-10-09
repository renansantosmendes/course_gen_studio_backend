"""Use case: read the profile of the authenticated user."""

from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    UserProfile,
)
from coursegen_backend.application.ports.unit_of_work import UnitOfWork


class GetCurrentUserProfileUseCase:
    """Returns the authenticated user with their organizations."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
    ) -> None:
        """Create the use case.

        Parameters
        ----------
        unit_of_work : UnitOfWork
            Transaction boundary and repositories.

        Returns
        -------
        None
        """
        self._unit_of_work = unit_of_work

    def execute(
        self,
        principal: AuthenticatedPrincipal,
    ) -> UserProfile:
        """Load the profile of the authenticated user.

        Parameters
        ----------
        principal : AuthenticatedPrincipal
            The authenticated user and session.

        Returns
        -------
        UserProfile
            The user and their organization memberships.
        """
        with self._unit_of_work as uow:
            memberships = uow.users.list_memberships(principal.user.id)
        return UserProfile(user=principal.user, memberships=memberships)
