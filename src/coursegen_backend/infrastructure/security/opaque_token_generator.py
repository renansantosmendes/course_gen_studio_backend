"""Random opaque tokens stored as SHA-256 digests."""

import hashlib
import secrets

from coursegen_backend.application.ports.security import (
    OpaqueTokenGenerator,
)


class SecretsOpaqueTokenGenerator(OpaqueTokenGenerator):
    """Generates tokens with the ``secrets`` module.

    A SHA-256 digest is enough to store these tokens because they carry
    high entropy, unlike passwords.
    """

    def __init__(
        self,
        token_bytes: int = 48,
    ) -> None:
        """Create the generator.

        Parameters
        ----------
        token_bytes : int
            Amount of random bytes in each token.

        Returns
        -------
        None
        """
        self._token_bytes = token_bytes

    def generate(self) -> str:
        """Create a new URL-safe random token.

        Returns
        -------
        str
            Token encoded in URL-safe base64.
        """
        return secrets.token_urlsafe(self._token_bytes)

    def hash(
        self,
        token: str,
    ) -> str:
        """Compute the SHA-256 digest of a token.

        Parameters
        ----------
        token : str
            Token in plain text.

        Returns
        -------
        str
            Hexadecimal digest.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
