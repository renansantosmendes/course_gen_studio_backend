"""Data structures exchanged between the use cases and their callers."""

from dataclasses import dataclass

from coursegen_backend.domain.entities import OrganizationMembership, User


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """The CourseGen user behind a valid access token.

    Attributes
    ----------
    user : User
        The CourseGen profile of the authenticated person.
    """

    user: User


@dataclass(frozen=True)
class UserProfile:
    """A user together with the organizations they belong to.

    Attributes
    ----------
    user : User
        The user profile.
    memberships : list[OrganizationMembership]
        Organizations and roles of the user.
    """

    user: User
    memberships: list[OrganizationMembership]
