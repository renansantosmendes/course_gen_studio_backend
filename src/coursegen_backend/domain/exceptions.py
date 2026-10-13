"""Business errors raised by CourseGen Studio.

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


class InvalidAccessTokenError(DomainError):
    """The access token is missing, malformed, expired or not trusted."""

    code = "invalid_access_token"
    message = "The access token is missing, invalid or expired."


class AccountDisabledError(DomainError):
    """The person was blocked from using CourseGen Studio."""

    code = "account_disabled"
    message = "This account is not allowed to use CourseGen Studio."


class AccountLinkConflictError(DomainError):
    """A CourseGen profile with the same e-mail belongs to another account.

    Happens when a profile created before the auth service existed uses
    the e-mail of a different auth service account; an administrator
    must merge or remove it.
    """

    code = "account_link_conflict"
    message = (
        "Another CourseGen Studio profile already uses this e-mail. "
        "Contact an administrator."
    )


class AuthServiceUnavailableError(DomainError):
    """The auth service's public keys could not be fetched."""

    code = "auth_service_unavailable"
    message = "The authentication service is unavailable. Try again later."
