"""Tests of the CourseGen identity entities."""

from dataclasses import replace

from tests.fakes import make_identity, make_user


def test_profile_matches_identity_ignoring_email_case() -> None:
    """E-mail comparison ignores letter case."""
    identity = make_identity()
    user = replace(make_user(identity), email=identity.email.upper())
    assert user.matches(identity)


def test_profile_does_not_match_changed_name_or_email() -> None:
    """A new name or e-mail in the auth service needs a refresh."""
    identity = make_identity()
    user = make_user(identity)
    assert not user.matches(replace(identity, full_name="Camila T."))
    assert not user.matches(replace(identity, email="new@example.com"))
