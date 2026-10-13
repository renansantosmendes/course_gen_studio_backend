"""Domain entities of CourseGen Studio's identity context."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VerifiedIdentity:
    """Who a valid access token issued by the auth service belongs to.

    Attributes
    ----------
    user_id : UUID
        Identifier of the account in the auth service (``sub`` claim).
        CourseGen uses the same value as the primary key of its users.
    email : str
        E-mail of the account (``email`` claim).
    full_name : str
        Name of the account (``name`` claim).
    """

    user_id: UUID
    email: str
    full_name: str


@dataclass(frozen=True)
class User:
    """CourseGen Studio's profile of an authenticated person.

    Attributes
    ----------
    id : UUID
        Same identifier as the account in the auth service.
    email : str
        E-mail, kept in sync with the auth service.
    full_name : str
        Name, kept in sync with the auth service.
    job_title : str | None
        Optional job title, for example "Instructional designer".
    is_active : bool
        Whether the person may use CourseGen Studio. Independent of the
        auth service: an administrator can block access to CourseGen
        only.
    """

    id: UUID
    email: str
    full_name: str
    job_title: str | None
    is_active: bool

    def matches(
        self,
        identity: VerifiedIdentity,
    ) -> bool:
        """Tell whether the profile already reflects an identity.

        Parameters
        ----------
        identity : VerifiedIdentity
            Identity read from a valid access token.

        Returns
        -------
        bool
            ``True`` when e-mail and name are up to date.
        """
        return (
            self.email.casefold() == identity.email.casefold()
            and self.full_name == identity.full_name
        )


@dataclass(frozen=True)
class OrganizationMembership:
    """The roles a user holds inside one organization (tenant).

    Attributes
    ----------
    organization_id : UUID
        Identifier of the organization.
    organization_name : str
        Display name of the organization.
    organization_slug : str
        URL-friendly unique name of the organization.
    roles : tuple[str, ...]
        Roles of the user in the organization: ``author``, ``reviewer``,
        ``curator`` and/or ``admin``.
    """

    organization_id: UUID
    organization_name: str
    organization_slug: str
    roles: tuple[str, ...]
