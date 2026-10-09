"""Business errors raised by the authentication context.

Every error carries a stable, machine-readable ``code`` and a
human-readable ``message``. The presentation layer decides how each one
is translated to the transport (for example, an HTTP status code).
"""


class DomainError(Exception):
    """Base class of every business error of the application.

    Attributes
    ----------
    code : str
        Stable identifier of the error, safe to use in client code.
    message : str
        Human-readable explanation, in English.
    """

    code = "domain_error"
    message = "The operation could not be completed."

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        """Create the error, optionally overriding the default message.

        Parameters
        ----------
        message : str | None
            Custom explanation. When omitted, the class default is used.

        Returns
        -------
        None
        """
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(DomainError):
    """The e-mail and password pair does not match an active account."""

    code = "invalid_credentials"
    message = "Invalid e-mail or password."


class TooManyLoginAttemptsError(DomainError):
    """Too many failed sign-in attempts were made in a short period.

    Attributes
    ----------
    retry_after_seconds : int
        How long the client should wait before trying again.
    """

    code = "too_many_login_attempts"
    message = "Too many failed sign-in attempts. Try again later."

    def __init__(
        self,
        retry_after_seconds: int,
    ) -> None:
        """Create the error with the waiting time the client must respect.

        Parameters
        ----------
        retry_after_seconds : int
            Seconds until a new attempt is allowed.

        Returns
        -------
        None
        """
        self.retry_after_seconds = retry_after_seconds
        super().__init__()


class InvalidAccessTokenError(DomainError):
    """The access token is missing, malformed, expired or revoked."""

    code = "invalid_access_token"
    message = "The access token is missing, invalid, expired or revoked."


class InvalidRefreshTokenError(DomainError):
    """The refresh token is unknown, expired or belongs to an ended
    session."""

    code = "invalid_refresh_token"
    message = "The refresh token is invalid, expired or revoked."


class InvalidPasswordResetTokenError(DomainError):
    """The password reset token is unknown, expired or already used."""

    code = "invalid_password_reset_token"
    message = "The password reset link is invalid, expired or already used."


class WeakPasswordError(DomainError):
    """The new password does not satisfy the password policy.

    Attributes
    ----------
    violations : list[str]
        One explanation for each rule that was broken.
    """

    code = "weak_password"
    message = "The password does not meet the password policy."

    def __init__(
        self,
        violations: list[str],
    ) -> None:
        """Create the error with the list of broken rules.

        Parameters
        ----------
        violations : list[str]
            Explanations of the rules the password does not satisfy.

        Returns
        -------
        None
        """
        self.violations = violations
        super().__init__()


class PasswordReuseError(DomainError):
    """The new password is the same as the current one."""

    code = "password_reuse"
    message = "The new password must be different from the current one."


class IncorrectCurrentPasswordError(DomainError):
    """The current password informed to change the password is wrong."""

    code = "incorrect_current_password"
    message = "The current password is incorrect."
