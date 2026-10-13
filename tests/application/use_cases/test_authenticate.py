"""Tests of the authentication and profile use cases."""

from dataclasses import replace

import pytest

from coursegen_backend.application.use_cases.authenticate import (
    AuthenticateUseCase,
)
from coursegen_backend.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from coursegen_backend.domain.exceptions import (
    AccountDisabledError,
    AccountLinkConflictError,
    InvalidAccessTokenError,
)
from coursegen_backend.infrastructure.security.jwks_access_token_verifier import (
    JwksAccessTokenVerifier,
)
from tests.conftest import issue_token
from tests.fakes import (
    InMemoryUnitOfWork,
    make_identity,
    make_membership,
    make_user,
)


@pytest.fixture
def use_case(
    unit_of_work: InMemoryUnitOfWork,
    access_token_verifier: JwksAccessTokenVerifier,
) -> AuthenticateUseCase:
    """Provide the authentication use case.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    access_token_verifier : JwksAccessTokenVerifier
        Verifier trusting the test key.

    Returns
    -------
    AuthenticateUseCase
        Use case under test.
    """
    return AuthenticateUseCase(
        unit_of_work=unit_of_work,
        access_token_verifier=access_token_verifier,
    )


def test_first_access_provisions_profile(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A new account gets a CourseGen profile with the token's data.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    principal = use_case.execute(issue_token(identity))
    assert principal.user.id == identity.user_id
    assert principal.user.email == identity.email
    assert principal.user.is_active
    assert unit_of_work.commits == 1


def test_current_profile_is_not_rewritten(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """Nothing is written when the profile is already in sync.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    unit_of_work.users.add(make_user(identity))
    principal = use_case.execute(issue_token(identity))
    assert principal.user.job_title == "Instructional designer"
    assert unit_of_work.commits == 0
    assert not unit_of_work.users.saved_identities


def test_changed_name_is_synced_keeping_local_fields(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A new name is copied; CourseGen-only fields are kept.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    unit_of_work.users.add(make_user(identity))
    renamed = replace(identity, full_name="Camila Torres Silva")
    principal = use_case.execute(issue_token(renamed))
    assert principal.user.full_name == "Camila Torres Silva"
    assert principal.user.job_title == "Instructional designer"
    assert unit_of_work.commits == 1


def test_disabled_profile_is_refused(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A valid token does not override a CourseGen block.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    unit_of_work.users.add(make_user(identity, is_active=False))
    with pytest.raises(AccountDisabledError):
        use_case.execute(issue_token(identity))


def test_email_of_another_profile_is_a_conflict(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A legacy profile with the same e-mail blocks the link.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    unit_of_work.users.add(make_user(make_identity()))
    with pytest.raises(AccountLinkConflictError):
        use_case.execute(issue_token(make_identity()))


def test_invalid_token_is_refused_before_touching_storage(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """Bad tokens never reach the repository.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    with pytest.raises(InvalidAccessTokenError):
        use_case.execute("not-a-jwt")
    assert not unit_of_work.users.users


def test_profile_lists_memberships(
    use_case: AuthenticateUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """The profile carries the organizations and roles.

    Parameters
    ----------
    use_case : AuthenticateUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    unit_of_work.users.add(make_user(identity), [make_membership()])
    principal = use_case.execute(issue_token(identity))
    profile = GetCurrentUserProfileUseCase(unit_of_work).execute(principal)
    assert profile.memberships[0].roles == ("author", "reviewer")
