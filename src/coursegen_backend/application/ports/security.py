"""Port that validates access tokens issued by the auth service."""

from abc import ABC, abstractmethod

from coursegen_backend.domain.entities import VerifiedIdentity


class AccessTokenVerifier(ABC):
    """Verifies access tokens and extracts the identity they carry."""

    @abstractmethod
    def verify(
        self,
        token: str,
    ) -> VerifiedIdentity:
        """Validate a token and return the identity it was issued to.

        Parameters
        ----------
        token : str
            Encoded access token from the ``Authorization`` header.

        Returns
        -------
        VerifiedIdentity
            Identifier, e-mail and name of the account.

        Raises
        ------
        InvalidAccessTokenError
            When the token is malformed, expired, signed by an untrusted
            key, or issued for another audience.
        """
