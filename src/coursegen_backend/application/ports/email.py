"""Port used to deliver e-mail messages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """A plain-text e-mail message.

    Attributes
    ----------
    recipient : str
        Destination e-mail address.
    subject : str
        Subject line.
    body : str
        Plain-text content.
    """

    recipient: str
    subject: str
    body: str


class EmailDeliveryError(Exception):
    """Raised by an ``EmailSender`` when a message cannot be delivered."""


class EmailSender(ABC):
    """Delivers e-mail messages to their recipients."""

    @abstractmethod
    def send(
        self,
        message: EmailMessage,
    ) -> None:
        """Deliver a message.

        Parameters
        ----------
        message : EmailMessage
            Message to deliver.

        Returns
        -------
        None

        Raises
        ------
        EmailDeliveryError
            When the message cannot be delivered.
        """
