"""Configurable policies used by the authentication use cases."""

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote


@dataclass(frozen=True)
class SessionPolicy:
    """Lifetimes of refresh tokens.

    Attributes
    ----------
    refresh_token_ttl : timedelta
        Lifetime of a session when the user did not ask to stay signed
        in.
    keep_signed_in_refresh_token_ttl : timedelta
        Lifetime of a session when the user asked to stay signed in.
    """

    refresh_token_ttl: timedelta = timedelta(hours=12)
    keep_signed_in_refresh_token_ttl: timedelta = timedelta(days=30)

    def refresh_token_ttl_for(
        self,
        keep_signed_in: bool,
    ) -> timedelta:
        """Choose the refresh token lifetime of a session.

        Parameters
        ----------
        keep_signed_in : bool
            Whether the user asked to stay signed in.

        Returns
        -------
        timedelta
            Lifetime to apply.
        """
        if keep_signed_in:
            return self.keep_signed_in_refresh_token_ttl
        return self.refresh_token_ttl


@dataclass(frozen=True)
class LoginThrottlePolicy:
    """Limits on failed sign-in attempts per account.

    Attributes
    ----------
    max_failed_attempts : int
        Failed attempts tolerated inside the window.
    window : timedelta
        Period over which failed attempts are counted.
    """

    max_failed_attempts: int = 5
    window: timedelta = timedelta(minutes=15)


@dataclass(frozen=True)
class PasswordResetPolicy:
    """Rules of the password recovery flow.

    Attributes
    ----------
    token_ttl : timedelta
        Lifetime of a reset link.
    reset_page_url : str
        Front-end page that receives the token and asks for the new
        password.
    """

    reset_page_url: str
    token_ttl: timedelta = timedelta(minutes=30)

    def build_reset_link(
        self,
        token: str,
    ) -> str:
        """Build the link sent by e-mail.

        The token goes in the URL fragment, which browsers never send to
        servers, so it does not leak into access logs or ``Referer``
        headers.

        Parameters
        ----------
        token : str
            Reset token in plain text.

        Returns
        -------
        str
            Absolute link to the reset page.

        Example
        -------
        >>> PasswordResetPolicy("https://app.edu/login").build_reset_link(
        ...     "abc"
        ... )
        'https://app.edu/login#reset_token=abc'
        """
        base_url = self.reset_page_url.split("#", 1)[0]
        return f"{base_url}#reset_token={quote(token, safe='')}"
