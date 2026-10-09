"""Tests of the password recovery e-mail composition."""

from coursegen_backend.application.services.password_reset_email import (
    PASSWORD_RESET_SUBJECT,
    build_password_reset_email,
)


def test_email_contains_link_first_name_and_validity() -> None:
    """The message greets by first name and explains the link."""
    message = build_password_reset_email(
        recipient="camila@uni.edu",
        full_name="Camila Torres",
        reset_link="https://app.edu/login#reset_token=abc",
        validity_minutes=30,
    )
    assert message.recipient == "camila@uni.edu"
    assert message.subject == PASSWORD_RESET_SUBJECT
    assert message.body.startswith("Olá, Camila.")
    assert "https://app.edu/login#reset_token=abc" in message.body
    assert "30 minutos" in message.body


def test_blank_name_does_not_break_greeting() -> None:
    """A blank name still produces a message."""
    message = build_password_reset_email(
        recipient="x@uni.edu",
        full_name=" ",
        reset_link="https://app.edu",
        validity_minutes=5,
    )
    assert "https://app.edu" in message.body
