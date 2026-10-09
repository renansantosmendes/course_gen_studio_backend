"""Credentials generated at import time for the test suite.

No password or key is written in the test code: every value below is
random for each run, so secret scanners have nothing to flag and no
test depends on a specific credential.
"""

import secrets

TEST_EMAIL = "user@example.com"


def generate_password() -> str:
    """Create a random password that satisfies the password policy.

    The ``Pw7`` prefix guarantees a letter and a digit; the hexadecimal
    tail cannot contain whitespace or the e-mail local part.

    Returns
    -------
    str
        Random password with 27 characters.
    """
    return f"Pw7{secrets.token_hex(12)}"


def generate_secret_key() -> str:
    """Create a random key long enough for HS256 signatures.

    Returns
    -------
    str
        URL-safe random key.
    """
    return secrets.token_urlsafe(48)


VALID_PASSWORD = generate_password()
NEW_PASSWORD = generate_password()
OTHER_NEW_PASSWORD = generate_password()
WRONG_PASSWORD = generate_password()
JWT_SECRET = generate_secret_key()
OTHER_JWT_SECRET = generate_secret_key()
SMTP_PASSWORD = generate_secret_key()
