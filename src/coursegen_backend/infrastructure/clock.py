"""Clock backed by the system time."""

from datetime import UTC, datetime

from coursegen_backend.application.ports.clock import Clock


class SystemClock(Clock):
    """Reads the current time from the operating system."""

    def now(self) -> datetime:
        """Return the current moment.

        Returns
        -------
        datetime
            Current moment, timezone-aware in UTC.
        """
        return datetime.now(UTC)
