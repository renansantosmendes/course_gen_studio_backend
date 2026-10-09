"""Tests of the application policies."""

from datetime import timedelta

from coursegen_backend.application.policies import (
    PasswordResetPolicy,
    SessionPolicy,
)


def test_session_policy_chooses_lifetime_by_keep_signed_in() -> None:
    """The long lifetime applies only when asked to stay signed in."""
    policy = SessionPolicy(
        refresh_token_ttl=timedelta(hours=1),
        keep_signed_in_refresh_token_ttl=timedelta(days=7),
    )
    assert policy.refresh_token_ttl_for(False) == timedelta(hours=1)
    assert policy.refresh_token_ttl_for(True) == timedelta(days=7)


def test_reset_link_carries_token_in_fragment() -> None:
    """The token goes after ``#`` so it never reaches servers."""
    policy = PasswordResetPolicy("https://app.edu/login.html")
    assert (
        policy.build_reset_link("a/b+c")
        == "https://app.edu/login.html#reset_token=a%2Fb%2Bc"
    )


def test_reset_link_replaces_existing_fragment() -> None:
    """A fragment already present in the page URL is discarded."""
    policy = PasswordResetPolicy("https://app.edu/login.html#old")
    assert policy.build_reset_link("abc").endswith(
        "login.html#reset_token=abc"
    )
