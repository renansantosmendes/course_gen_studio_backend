"""Password hashing with Argon2id."""

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError

from coursegen_backend.application.ports.security import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Hashes passwords with Argon2id, the OWASP-recommended algorithm."""

    def __init__(
        self,
        time_cost: int = 3,
        memory_cost: int = 65536,
        parallelism: int = 4,
    ) -> None:
        """Create the hasher.

        Parameters
        ----------
        time_cost : int
            Number of iterations.
        memory_cost : int
            Memory usage, in kibibytes.
        parallelism : int
            Number of parallel lanes.

        Returns
        -------
        None
        """
        self._hasher = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
        )
        self._dummy_hash = self._hasher.hash("coursegen-dummy-password")

    def hash(
        self,
        password: str,
    ) -> str:
        """Compute a salted Argon2id hash of a password.

        Parameters
        ----------
        password : str
            Password in plain text.

        Returns
        -------
        str
            Encoded hash in the PHC string format.
        """
        return self._hasher.hash(password)

    def verify(
        self,
        password_hash: str,
        password: str,
    ) -> bool:
        """Check whether a password matches a stored hash.

        Parameters
        ----------
        password_hash : str
            Stored hash.
        password : str
            Password in plain text.

        Returns
        -------
        bool
            ``True`` when the password matches; ``False`` when it does
            not or when the hash is malformed.
        """
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(
        self,
        password_hash: str,
    ) -> bool:
        """Tell whether a hash uses parameters other than the current ones.

        Parameters
        ----------
        password_hash : str
            Stored hash.

        Returns
        -------
        bool
            ``True`` when the hash should be recomputed.
        """
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True

    def simulate_verification(
        self,
        password: str,
    ) -> None:
        """Verify the password against a fixed hash and ignore the result.

        Parameters
        ----------
        password : str
            Password in plain text.

        Returns
        -------
        None
        """
        self.verify(self._dummy_hash, password)
