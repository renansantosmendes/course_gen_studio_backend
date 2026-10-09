"""Chooses the e-mail sender configured in the settings."""

from coursegen_backend.application.ports.email import EmailSender
from coursegen_backend.infrastructure.config import Settings
from coursegen_backend.infrastructure.email.logging_email_sender import (
    LoggingEmailSender,
)
from coursegen_backend.infrastructure.email.smtp_email_sender import (
    SmtpEmailSender,
)


def build_email_sender(settings: Settings) -> EmailSender:
    """Create the e-mail sender selected by ``EMAIL_BACKEND``.

    Parameters
    ----------
    settings : Settings
        Application settings.

    Returns
    -------
    EmailSender
        An SMTP sender, or a logging sender in development.

    Raises
    ------
    ValueError
        When SMTP is selected without host or sender address.
    """
    if settings.email_backend == "console":
        return LoggingEmailSender()
    if not settings.smtp_host or not settings.smtp_sender:
        raise ValueError(
            "SMTP_HOST and SMTP_SENDER are required when EMAIL_BACKEND "
            "is 'smtp'."
        )
    return SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_sender,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value()
        if settings.smtp_password
        else None,
        use_tls=settings.smtp_use_tls,
    )
