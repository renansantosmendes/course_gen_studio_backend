"""E-mail sender that only writes messages to the application log."""

import logging

from coursegen_backend.application.ports.email import (
    EmailMessage,
    EmailSender,
)

logger = logging.getLogger(__name__)


class LoggingEmailSender(EmailSender):
    """Logs messages instead of sending them; meant for development.

    Never use it in production: the log would contain the password
    reset links.
    """

    def send(
        self,
        message: EmailMessage,
    ) -> None:
        """Write the message to the log at ``INFO`` level.

        Parameters
        ----------
        message : EmailMessage
            Message to log.

        Returns
        -------
        None
        """
        logger.info(
            "E-mail to %s | %s\n%s",
            message.recipient,
            message.subject,
            message.body,
        )
