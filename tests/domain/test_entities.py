"""Tests of the authentication domain entities."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from coursegen_backend.domain.entities import PasswordResetToken, UserSession
from tests.fakes import DEFAULT_MOMENT, make_user


def make_session() -> UserSession:
    """Build a session expiring one hour after the default moment.

    Returns
    -------
    UserSession
        Open session.
    """
    return UserSession(
        id=uuid4(),
        user_id=uuid4(),
        keep_signed_in=False,
        created_at=DEFAULT_MOMENT,
        expires_at=DEFAULT_MOMENT + timedelta(hours=1),
        revoked_at=None,
    )


def test_active_user_with_password_can_sign_in_with_password() -> None:
    """An active account with a hash may use password sign-in."""
    assert make_user().can_sign_in_with_password


def test_inactive_user_cannot_sign_in_with_password() -> None:
    """A deactivated account may not sign in."""
    assert not make_user(is_active=False).can_sign_in_with_password


def test_sso_only_user_cannot_sign_in_with_password() -> None:
    """An account without a password hash may not use passwords."""
    assert not make_user(password=None).can_sign_in_with_password


def test_session_is_active_before_expiration() -> None:
    """An open session is active before it expires."""
    assert make_session().is_active(DEFAULT_MOMENT)


def test_session_is_inactive_at_expiration() -> None:
    """A session stops being active at its expiration moment."""
    session = make_session()
    assert not session.is_active(session.expires_at)


def test_revoked_session_is_inactive() -> None:
    """A revoked session is never active."""
    session = replace(make_session(), revoked_at=DEFAULT_MOMENT)
    assert not session.is_active(DEFAULT_MOMENT)


def test_reset_token_usable_until_expiration() -> None:
    """A fresh token is usable only before its expiration."""
    token = PasswordResetToken(
        id=uuid4(),
        user_id=uuid4(),
        expires_at=DEFAULT_MOMENT + timedelta(minutes=30),
        used_at=None,
    )
    assert token.is_usable(DEFAULT_MOMENT)
    assert not token.is_usable(token.expires_at)


def test_used_reset_token_is_not_usable() -> None:
    """A consumed token cannot be redeemed again."""
    token = PasswordResetToken(
        id=uuid4(),
        user_id=uuid4(),
        expires_at=DEFAULT_MOMENT + timedelta(minutes=30),
        used_at=DEFAULT_MOMENT,
    )
    assert not token.is_usable(DEFAULT_MOMENT)
