"""Persistence ports of CourseGen Studio's identity context."""

from abc import ABC, abstractmethod
from uuid import UUID

from coursegen_backend.domain.entities import (
    OrganizationMembership,
    User,
    VerifiedIdentity,
)


class UserRepository(ABC):
    """Reads and provisions CourseGen user profiles."""

    @abstractmethod
    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        """Find a profile by identifier.

        Parameters
        ----------
        user_id : UUID
            Identifier shared with the auth service.

        Returns
        -------
        User | None
            The profile, or ``None`` when it does not exist yet.
        """

    @abstractmethod
    def save_identity(
        self,
        identity: VerifiedIdentity,
    ) -> User:
        """Create the profile of an identity, or refresh its e-mail and name.

        Parameters
        ----------
        identity : VerifiedIdentity
            Identity read from a valid access token.

        Returns
        -------
        User
            The stored profile.

        Raises
        ------
        AccountLinkConflictError
            When another profile already uses the identity's e-mail.
        """

    @abstractmethod
    def list_memberships(
        self,
        user_id: UUID,
    ) -> list[OrganizationMembership]:
        """List the organizations of a user and the roles held in each.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        list[OrganizationMembership]
            Memberships ordered by organization name.
        """
