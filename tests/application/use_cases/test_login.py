"""Tests of the sign-in use case."""

from datetime import timedelta

import pytest

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import RequestContext
from coursegen_backend.application.policies import LoginThrottlePolicy
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.application.use_cases.login import LoginUseCase
from coursegen_backend.domain.exceptions import (
    InvalidCredentialsError,
    TooManyLoginAttemptsError,
)
from tests.fakes import (
    FakeClock,
    FakePasswordHasher,
    InMemoryUnitOfWork,
    make_membership,
    make_user,
)
from tests.credentials import (
    TEST_EMAIL,
    VALID_PASSWORD,
    WRONG_PASSWORD,
)

CONTEXT = RequestContext(ip_address="203.0.113.7", user_agent="pytest")


@pytest.fixture
def use_case(
    unit_of_work: InMemoryUnitOfWork,
    password_hasher: FakePasswordHasher,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> LoginUseCase:
    """Provide the use case with a 3-failure throttle.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    password_hasher : FakePasswordHasher
        Fake hasher.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    LoginUseCase
        Use case under test.
    """
    return LoginUseCase(
        unit_of_work=unit_of_work,
        password_hasher=password_hasher,
        session_token_issuer=session_token_issuer,
        throttle_policy=LoginThrottlePolicy(
            max_failed_attempts=3,
            window=timedelta(minutes=15),
        ),
        clock=clock,
    )


def test_successful_login_opens_session_and_returns_profile(
    use_case: LoginUseCase,
    unit_of_work: InMemoryUnitOfWork,
    clock: FakeClock,
) -> None:
    """Valid credentials open a session and return memberships.

    Parameters
    ----------
    use_case : LoginUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    membership = make_membership()
    user = unit_of_work.users.add(make_user(), [membership])
    result = use_case.execute(
        email=TEST_EMAIL.upper(),
        password=VALID_PASSWORD,
        keep_signed_in=True,
        context=CONTEXT,
    )
    assert result.profile.user.id == user.id
    assert result.profile.user.last_login_at == clock.now()
    assert result.profile.memberships == [membership]
    assert result.tokens.session_id in unit_of_work.sessions.sessions
    assert unit_of_work.audit_log.actions == [audit_actions.LOGIN_SUCCEEDED]
    assert unit_of_work.commits == 1


def test_wrong_password_is_rejected_and_audited(
    use_case: LoginUseCase,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A wrong password fails and records the attempt for the account.

    Parameters
    ----------
    use_case : LoginUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    user = unit_of_work.users.add(make_user())
    with pytest.raises(InvalidCredentialsError):
        use_case.execute(user.email, WRONG_PASSWORD, False, CONTEXT)
    event, _ = unit_of_work.audit_log.entries[0]
    assert event.action == audit_actions.LOGIN_FAILED
    assert event.entity_id == user.id
    assert not unit_of_work.sessions.sessions
    assert unit_of_work.commits == 1


def test_unknown_email_is_rejected_with_simulated_verification(
    use_case: LoginUseCase,
    unit_of_work: InMemoryUnitOfWork,
    password_hasher: FakePasswordHasher,
) -> None:
    """Unknown e-mails fail like wrong passwords, spending hash time.

    Parameters
    ----------
    use_case : LoginUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    password_hasher : FakePasswordHasher
        Fake hasher recording simulated checks.

    Returns
    -------
    None
    """
    with pytest.raises(InvalidCredentialsError):
        use_case.execute("nobody@uni.edu", "whatever123", False, CONTEXT)
    assert password_hasher.simulated_verifications == 1
    event, _ = unit_of_work.audit_log.entries[0]
    assert event.entity_id is None
    assert event.details == {"email": "nobody@uni.edu"}


@pytest.mark.parametrize(
    "user_factory_arguments",
    [{"is_active": False}, {"password": None}],
)
def test_inactive_or_sso_only_accounts_cannot_sign_in(
    use_case: LoginUseCase,
    unit_of_work: InMemoryUnitOfWork,
    user_factory_arguments: dict,
) -> None:
    """Inactive and password-less accounts get the generic error.

    Parameters
    ----------
    use_case : LoginUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    user_factory_arguments : dict
        Arguments that make the account unable to sign in.

    Returns
    -------
    None
    """
    user = unit_of_work.users.add(make_user(**user_factory_arguments))
    with pytest.raises(InvalidCredentialsError):
        use_case.execute(user.email, VALID_PASSWORD, False, CONTEXT)


def test_account_is_throttled_after_too_many_failures(
    use_case: LoginUseCase,
    unit_of_work: InMemoryUnitOfWork,
    clock: FakeClock,
) -> None:
    """After the limit, even the right password is refused for a while.

    Parameters
    ----------
    use_case : LoginUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = unit_of_work.users.add(make_user())
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            use_case.execute(user.email, WRONG_PASSWORD, False, CONTEXT)
    with pytest.raises(TooManyLoginAttemptsError) as error_info:
        use_case.execute(user.email, VALID_PASSWORD, False, CONTEXT)
    assert error_info.value.retry_after_seconds == 900
    clock.advance(timedelta(minutes=16))
    result = use_case.execute(
        user.email,
        VALID_PASSWORD,
        False,
        CONTEXT,
    )
    assert result.profile.user.id == user.id


def test_outdated_hash_is_upgraded_on_login(
    unit_of_work: InMemoryUnitOfWork,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """A hash with old parameters is recomputed after a valid sign-in.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = unit_of_work.users.add(make_user())
    hasher = FakePasswordHasher(outdated_hashes={user.password_hash})
    use_case = LoginUseCase(
        unit_of_work=unit_of_work,
        password_hasher=hasher,
        session_token_issuer=session_token_issuer,
        throttle_policy=LoginThrottlePolicy(),
        clock=clock,
    )
    hasher.hash = lambda password: f"argon2-new:{password}"
    use_case.execute(user.email, VALID_PASSWORD, False, CONTEXT)
    assert (
        unit_of_work.users.get_by_id(user.id).password_hash
        == f"argon2-new:{VALID_PASSWORD}"
    )
