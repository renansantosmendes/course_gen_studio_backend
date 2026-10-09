"""Rules a password must satisfy to be accepted."""

from dataclasses import dataclass

from coursegen_backend.domain.exceptions import WeakPasswordError


@dataclass(frozen=True)
class PasswordPolicy:
    """Password strength rules applied when a password is defined.

    Attributes
    ----------
    min_length : int
        Minimum number of characters.
    max_length : int
        Maximum number of characters, which bounds hashing cost.
    """

    min_length: int = 10
    max_length: int = 128

    def find_violations(
        self,
        password: str,
        email: str,
    ) -> list[str]:
        """List every rule the password breaks.

        Parameters
        ----------
        password : str
            Candidate password, in plain text.
        email : str
            E-mail of the account, which must not be part of the
            password.

        Returns
        -------
        list[str]
            Explanations of the broken rules; empty when the password is
            acceptable.

        Example
        -------
        >>> PasswordPolicy().find_violations("short", "ana@uni.edu")
        ['Password must have at least 10 characters.', ...]
        """
        violations = []
        if len(password) < self.min_length:
            violations.append(
                f"Password must have at least {self.min_length} characters."
            )
        if len(password) > self.max_length:
            violations.append(
                f"Password must have at most {self.max_length} characters."
            )
        if not any(character.isalpha() for character in password):
            violations.append("Password must contain at least one letter.")
        if not any(character.isdigit() for character in password):
            violations.append("Password must contain at least one digit.")
        if password.strip() != password:
            violations.append(
                "Password must not start or end with whitespace."
            )
        local_part = email.split("@", 1)[0].casefold()
        if len(local_part) >= 3 and local_part in password.casefold():
            violations.append(
                "Password must not contain the e-mail address."
            )
        return violations

    def validate(
        self,
        password: str,
        email: str,
    ) -> None:
        """Ensure the password satisfies every rule of the policy.

        Parameters
        ----------
        password : str
            Candidate password, in plain text.
        email : str
            E-mail of the account the password belongs to.

        Returns
        -------
        None

        Raises
        ------
        WeakPasswordError
            When at least one rule is broken.
        """
        violations = self.find_violations(password, email)
        if violations:
            raise WeakPasswordError(violations)
