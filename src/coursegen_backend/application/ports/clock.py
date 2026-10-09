"""Port that provides the current time."""

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Source of the current moment, replaceable in tests."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current moment.

        Returns
        -------
        datetime
            Current timezone-aware moment, in UTC.
        """
