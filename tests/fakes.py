"""In-memory test doubles for the application ports."""

from dataclasses import replace
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

from coursegen_backend.application.ports.repositories import UserRepository
from coursegen_backend.application.ports.unit_of_work import UnitOfWork
from coursegen_backend.domain.entities import (
    OrganizationMembership,
    User,
    VerifiedIdentity,
)
from coursegen_backend.domain.exceptions import AccountLinkConflictError

TEST_EMAIL = "camila.torres@example.com"


class InMemoryUserRepository(UserRepository):
    """User repository backed by dictionaries."""

    def __init__(self) -> None:
        """Create an empty repository.

        Returns
        -------
        None
        """
        self.users = {}
        self.memberships = {}
        self.saved_identities = []

    def add(
        self,
        user: User,
        memberships: list[OrganizationMembership] | None = None,
    ) -> User:
        """Store a profile for the test.

        Parameters
        ----------
        user : User
            Profile to store.
        memberships : list[OrganizationMembership] | None
            Organizations of the user.

        Returns
        -------
        User
            The stored profile.
        """
        self.users[user.id] = user
        self.memberships[user.id] = memberships or []
        return user

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        """Find a profile by identifier.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        User | None
            The profile, if any.
        """
        return self.users.get(user_id)

    def save_identity(
        self,
        identity: VerifiedIdentity,
    ) -> User:
        """Insert or refresh a profile, rejecting e-mails of other users.

        Parameters
        ----------
        identity : VerifiedIdentity
            Identity read from a token.

        Returns
        -------
        User
            The stored profile.

        Raises
        ------
        AccountLinkConflictError
            When another profile uses the e-mail, ignoring case.
        """
        for user in self.users.values():
            if (
                user.id != identity.user_id
                and user.email.casefold() == identity.email.casefold()
            ):
                raise AccountLinkConflictError()
        self.saved_identities.append(identity)
        current = self.users.get(identity.user_id)
        if current is None:
            stored = User(
                id=identity.user_id,
                email=identity.email,
                full_name=identity.full_name,
                job_title=None,
                is_active=True,
            )
        else:
            stored = replace(
                current,
                email=identity.email,
                full_name=identity.full_name,
            )
        self.users[stored.id] = stored
        return stored

    def list_memberships(
        self,
        user_id: UUID,
    ) -> list[OrganizationMembership]:
        """Return the stored memberships.

        Parameters
        ----------
        user_id : UUID
            Identifier of the user.

        Returns
        -------
        list[OrganizationMembership]
            Memberships of the user.
        """
        return list(self.memberships.get(user_id, []))


class InMemoryUnitOfWork(UnitOfWork):
    """Unit of work over in-memory repositories that counts commits."""

    def __init__(self) -> None:
        """Create the unit of work and its repository.

        Returns
        -------
        None
        """
        self.users = InMemoryUserRepository()
        self.commits = 0

    def __enter__(self) -> Self:
        """Begin the fake transaction.

        Returns
        -------
        Self
            The unit of work.
        """
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """End the fake transaction.

        Parameters
        ----------
        exception_type : type[BaseException] | None
            Type of the raised exception, if any.
        exception : BaseException | None
            Raised exception, if any.
        traceback : TracebackType | None
            Traceback, if any.

        Returns
        -------
        None
        """

    def commit(self) -> None:
        """Count the commit.

        Returns
        -------
        None
        """
        self.commits += 1


def make_identity(
    email: str = TEST_EMAIL,
    full_name: str = "Camila Torres",
) -> VerifiedIdentity:
    """Build an identity as read from a valid token.

    Parameters
    ----------
    email : str
        E-mail of the account.
    full_name : str
        Name of the account.

    Returns
    -------
    VerifiedIdentity
        A new identity.
    """
    return VerifiedIdentity(user_id=uuid4(), email=email, full_name=full_name)


def make_user(
    identity: VerifiedIdentity,
    is_active: bool = True,
) -> User:
    """Build the CourseGen profile of an identity.

    Parameters
    ----------
    identity : VerifiedIdentity
        Identity the profile belongs to.
    is_active : bool
        Whether the person may use CourseGen.

    Returns
    -------
    User
        A profile already in sync with the identity.
    """
    return User(
        id=identity.user_id,
        email=identity.email,
        full_name=identity.full_name,
        job_title="Instructional designer",
        is_active=is_active,
    )


def make_membership() -> OrganizationMembership:
    """Build an organization membership.

    Returns
    -------
    OrganizationMembership
        Membership with the ``author`` and ``reviewer`` roles.
    """
    return OrganizationMembership(
        organization_id=uuid4(),
        organization_name="Universidade Exemplo",
        organization_slug="universidade-exemplo",
        roles=("author", "reviewer"),
    )
