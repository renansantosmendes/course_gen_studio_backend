"""Tests of the password recovery and change use cases."""

from datetime import timedelta

import pytest

from coursegen_backend.application import audit_actions
from coursegen_backend.application.dto import (
    AuthenticatedPrincipal,
    RequestContext,
)
from coursegen_backend.application.policies import PasswordResetPolicy
from coursegen_backend.application.services.session_token_issuer import (
    SessionTokenIssuer,
)
from coursegen_backend.application.use_cases.change_password import (
    ChangePasswordUseCase,
)
from coursegen_backend.application.use_cases.request_password_reset import (
    RequestPasswordResetUseCase,
)
from coursegen_backend.application.use_cases.reset_password import (
    ResetPasswordUseCase,
)
from coursegen_backend.domain.entities import User
from coursegen_backend.domain.exceptions import (
    IncorrectCurrentPasswordError,
    InvalidPasswordResetTokenError,
    PasswordReuseError,
    WeakPasswordError,
)
from coursegen_backend.domain.password_policy import PasswordPolicy
from coursegen_backend.infrastructure.security.opaque_token_generator import (
    SecretsOpaqueTokenGenerator,
)
from tests.fakes import (
    FakeClock,
    FakePasswordHasher,
    InMemoryUnitOfWork,
    RecordingEmailSender,
    make_user,
)

CONTEXT = RequestContext(ip_address="203.0.113.7")
RESET_PAGE = "https://app.edu/coursegen-login.html"


def build_request_use_case(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    email_sender: RecordingEmailSender,
    clock: FakeClock,
) -> RequestPasswordResetUseCase:
    """Create the recovery request use case.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    email_sender : RecordingEmailSender
        Recording e-mail sender.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    RequestPasswordResetUseCase
        Use case under test.
    """
    return RequestPasswordResetUseCase(
        unit_of_work=unit_of_work,
        token_generator=token_generator,
        email_sender=email_sender,
        reset_policy=PasswordResetPolicy(reset_page_url=RESET_PAGE),
        clock=clock,
    )


def extract_token(email_sender: RecordingEmailSender) -> str:
    """Read the reset token from the last e-mail sent.

    Parameters
    ----------
    email_sender : RecordingEmailSender
        Sender holding the messages.

    Returns
    -------
    str
        Token found in the link.
    """
    body = email_sender.messages[-1].body
    return body.split("#reset_token=", 1)[1].split()[0]


@pytest.fixture
def reset_use_case(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    password_hasher: FakePasswordHasher,
    clock: FakeClock,
) -> ResetPasswordUseCase:
    """Provide the password reset use case.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    password_hasher : FakePasswordHasher
        Fake hasher.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    ResetPasswordUseCase
        Use case under test.
    """
    return ResetPasswordUseCase(
        unit_of_work=unit_of_work,
        token_generator=token_generator,
        password_hasher=password_hasher,
        password_policy=PasswordPolicy(),
        clock=clock,
    )


def request_reset_for(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
    user: User,
) -> str:
    """Store a user, request a reset and return the e-mailed token.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    clock : FakeClock
        Frozen clock.
    user : User
        User requesting the reset.

    Returns
    -------
    str
        Reset token in plain text.
    """
    unit_of_work.users.add(user)
    email_sender = RecordingEmailSender()
    build_request_use_case(
        unit_of_work,
        token_generator,
        email_sender,
        clock,
    ).execute(user.email, CONTEXT)
    return extract_token(email_sender)


def test_request_sends_link_and_stores_only_hash(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
) -> None:
    """The e-mail carries the token; storage keeps only its hash.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    token = request_reset_for(
        unit_of_work,
        token_generator,
        clock,
        make_user(),
    )
    stored = unit_of_work.password_reset_tokens.tokens
    assert token not in stored
    assert token_generator.hash(token) in stored
    assert stored[token_generator.hash(token)].expires_at == (
        clock.now() + timedelta(minutes=30)
    )
    assert unit_of_work.audit_log.actions == [
        audit_actions.PASSWORD_RESET_REQUESTED
    ]


@pytest.mark.parametrize(
    "user",
    [None, make_user(is_active=False), make_user(password=None)],
)
def test_request_is_silent_when_account_cannot_reset(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
    user: User | None,
) -> None:
    """Unknown, inactive and SSO-only accounts get no e-mail.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    clock : FakeClock
        Frozen clock.
    user : User | None
        Account that cannot reset, or ``None`` for an unknown e-mail.

    Returns
    -------
    None
    """
    if user is not None:
        unit_of_work.users.add(user)
    email_sender = RecordingEmailSender()
    build_request_use_case(
        unit_of_work,
        token_generator,
        email_sender,
        clock,
    ).execute(user.email if user else "nobody@uni.edu", CONTEXT)
    assert not email_sender.messages
    assert not unit_of_work.password_reset_tokens.tokens


def test_request_swallows_delivery_failures(
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
) -> None:
    """A broken e-mail server does not reveal the account exists.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = unit_of_work.users.add(make_user())
    build_request_use_case(
        unit_of_work,
        token_generator,
        RecordingEmailSender(should_fail=True),
        clock,
    ).execute(user.email, CONTEXT)
    assert len(unit_of_work.password_reset_tokens.tokens) == 1


def test_reset_replaces_password_and_ends_sessions(
    reset_use_case: ResetPasswordUseCase,
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """Resetting changes the hash, burns tokens and revokes sessions.

    Parameters
    ----------
    reset_use_case : ResetPasswordUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    session_token_issuer : SessionTokenIssuer
        Session token issuer.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    user = make_user()
    token = request_reset_for(unit_of_work, token_generator, clock, user)
    session = session_token_issuer.open_session(
        unit_of_work,
        user,
        False,
        CONTEXT,
        clock.now(),
    )
    reset_use_case.execute(token, "NovaSenhaSegura2026", CONTEXT)
    assert (
        unit_of_work.users.get_by_id(user.id).password_hash
        == "hashed:NovaSenhaSegura2026"
    )
    assert unit_of_work.sessions.get_by_id(session.session_id).revoked_at
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_use_case.execute(token, "OutraSenha2026x", CONTEXT)
    assert audit_actions.PASSWORD_RESET_COMPLETED in (
        unit_of_work.audit_log.actions
    )


def test_reset_rejects_expired_token(
    reset_use_case: ResetPasswordUseCase,
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
) -> None:
    """Tokens stop working after their lifetime.

    Parameters
    ----------
    reset_use_case : ResetPasswordUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    token = request_reset_for(
        unit_of_work,
        token_generator,
        clock,
        make_user(),
    )
    clock.advance(timedelta(minutes=31))
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_use_case.execute(token, "NovaSenhaSegura2026", CONTEXT)


def test_reset_enforces_policy_and_rejects_reuse(
    reset_use_case: ResetPasswordUseCase,
    unit_of_work: InMemoryUnitOfWork,
    token_generator: SecretsOpaqueTokenGenerator,
    clock: FakeClock,
) -> None:
    """Weak or unchanged passwords keep the token usable.

    Parameters
    ----------
    reset_use_case : ResetPasswordUseCase
        Use case under test.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    token_generator : SecretsOpaqueTokenGenerator
        Token generator.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    None
    """
    token = request_reset_for(
        unit_of_work,
        token_generator,
        clock,
        make_user(),
    )
    with pytest.raises(WeakPasswordError):
        reset_use_case.execute(token, "short", CONTEXT)
    with pytest.raises(PasswordReuseError):
        reset_use_case.execute(token, "Planejamento2026", CONTEXT)
    reset_use_case.execute(token, "NovaSenhaSegura2026", CONTEXT)


def test_change_password_keeps_current_session_only(
    unit_of_work: InMemoryUnitOfWork,
    password_hasher: FakePasswordHasher,
    session_token_issuer: SessionTokenIssuer,
    clock: FakeClock,
) -> None:
    """Changing the password ends every other session.

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
    None
    """
    user = unit_of_work.users.add(make_user())
    current = session_token_issuer.open_session(
        unit_of_work,
        user,
        False,
        CONTEXT,
        clock.now(),
    )
    other = session_token_issuer.open_session(
        unit_of_work,
        user,
        True,
        CONTEXT,
        clock.now(),
    )
    use_case = ChangePasswordUseCase(
        unit_of_work=unit_of_work,
        password_hasher=password_hasher,
        password_policy=PasswordPolicy(),
        clock=clock,
    )
    use_case.execute(
        principal=AuthenticatedPrincipal(
            user=user,
            session_id=current.session_id,
        ),
        current_password="Planejamento2026",
        new_password="NovaSenhaSegura2026",
        context=CONTEXT,
    )
    sessions = unit_of_work.sessions
    assert sessions.get_by_id(current.session_id).revoked_at is None
    assert sessions.get_by_id(other.session_id).revoked_at is not None
    assert unit_of_work.audit_log.actions == [audit_actions.PASSWORD_CHANGED]


@pytest.mark.parametrize(
    ("current_password", "new_password", "expected_error"),
    [
        ("wrong-password1", "NovaSenhaSegura2026", IncorrectCurrentPasswordError),
        ("Planejamento2026", "short", WeakPasswordError),
        ("Planejamento2026", "Planejamento2026", PasswordReuseError),
    ],
)
def test_change_password_errors(
    unit_of_work: InMemoryUnitOfWork,
    password_hasher: FakePasswordHasher,
    clock: FakeClock,
    current_password: str,
    new_password: str,
    expected_error: type[Exception],
) -> None:
    """Wrong current, weak or unchanged passwords are refused.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    password_hasher : FakePasswordHasher
        Fake hasher.
    clock : FakeClock
        Frozen clock.
    current_password : str
        Informed current password.
    new_password : str
        Informed new password.
    expected_error : type[Exception]
        Error expected.

    Returns
    -------
    None
    """
    user = unit_of_work.users.add(make_user())
    use_case = ChangePasswordUseCase(
        unit_of_work=unit_of_work,
        password_hasher=password_hasher,
        password_policy=PasswordPolicy(),
        clock=clock,
    )
    with pytest.raises(expected_error):
        use_case.execute(
            principal=AuthenticatedPrincipal(user=user, session_id=user.id),
            current_password=current_password,
            new_password=new_password,
            context=CONTEXT,
        )
    assert unit_of_work.commits == 0
