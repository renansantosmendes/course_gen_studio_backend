"""Tests of the e-mail senders and their factory."""

import logging
from unittest.mock import MagicMock

import pytest

from coursegen_backend.application.ports.email import EmailMessage
from coursegen_backend.infrastructure.config import Settings
from coursegen_backend.infrastructure.email import smtp_email_sender
from coursegen_backend.infrastructure.email.factory import (
    build_email_sender,
)
from coursegen_backend.infrastructure.email.logging_email_sender import (
    LoggingEmailSender,
)
from coursegen_backend.infrastructure.email.smtp_email_sender import (
    SmtpEmailSender,
)

MESSAGE = EmailMessage(
    recipient="camila@uni.edu",
    subject="Assunto",
    body="Corpo",
)


def build_settings(**overrides: object) -> Settings:
    """Create settings without reading the environment.

    Parameters
    ----------
    **overrides : object
        Settings to override.

    Returns
    -------
    Settings
        Settings for the test.
    """
    values = {
        "COURSEGEN_DATABASE_URL": "postgresql://localhost/test",
        "COURSEGEN_JWT_SECRET_KEY": "secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_logging_sender_writes_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The development sender logs recipient, subject and body.

    Parameters
    ----------
    caplog : pytest.LogCaptureFixture
        Log capture.

    Returns
    -------
    None
    """
    with caplog.at_level(logging.INFO):
        LoggingEmailSender().send(MESSAGE)
    assert "camila@uni.edu" in caplog.text
    assert "Corpo" in caplog.text


def test_smtp_sender_uses_starttls_and_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SMTP sender upgrades to TLS, logs in and sends.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Replaces ``smtplib.SMTP``.

    Returns
    -------
    None
    """
    smtp_class = MagicMock()
    client = smtp_class.return_value.__enter__.return_value
    monkeypatch.setattr(smtp_email_sender.smtplib, "SMTP", smtp_class)
    SmtpEmailSender(
        host="smtp.uni.edu",
        port=587,
        sender="no-reply@uni.edu",
        username="user",
        password="pass",
    ).send(MESSAGE)
    smtp_class.assert_called_once_with("smtp.uni.edu", 587, timeout=10)
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("user", "pass")
    sent = client.send_message.call_args.args[0]
    assert sent["To"] == "camila@uni.edu"
    assert sent["From"] == "no-reply@uni.edu"


def test_factory_selects_backend() -> None:
    """``EMAIL_BACKEND`` chooses between console and SMTP."""
    assert isinstance(build_email_sender(build_settings()), LoggingEmailSender)
    smtp_sender = build_email_sender(
        build_settings(
            email_backend="smtp",
            smtp_host="smtp.uni.edu",
            smtp_sender="no-reply@uni.edu",
            smtp_password="pass",
        )
    )
    assert isinstance(smtp_sender, SmtpEmailSender)


def test_factory_requires_smtp_host_and_sender() -> None:
    """SMTP without host or sender is a configuration error."""
    with pytest.raises(ValueError):
        build_email_sender(build_settings(email_backend="smtp"))
