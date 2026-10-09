"""Tests of the password policy."""

import pytest

from coursegen_backend.domain.exceptions import WeakPasswordError
from coursegen_backend.domain.password_policy import PasswordPolicy

EMAIL = "camila.torres@instituicao.edu.br"


def test_strong_password_has_no_violations() -> None:
    """A long password with letters and digits is accepted."""
    assert not PasswordPolicy().find_violations("NovaSenha2026", EMAIL)


@pytest.mark.parametrize(
    ("password", "expected_fragment"),
    [
        ("abc123", "at least 10 characters"),
        ("a1" * 65, "at most 128 characters"),
        ("1234567890", "at least one letter"),
        ("SomenteLetras", "at least one digit"),
        (" NovaSenha2026", "whitespace"),
        ("camila.torres2026", "e-mail"),
    ],
)
def test_each_rule_is_reported(
    password: str,
    expected_fragment: str,
) -> None:
    """Every broken rule produces an explanation.

    Parameters
    ----------
    password : str
        Password breaking one rule.
    expected_fragment : str
        Text expected in the explanation.

    Returns
    -------
    None
    """
    violations = PasswordPolicy().find_violations(password, EMAIL)
    assert any(expected_fragment in violation for violation in violations)


def test_short_email_local_part_is_not_checked() -> None:
    """Local parts shorter than three characters are ignored."""
    assert not PasswordPolicy().find_violations("ab12345678", "ab@x.com")


def test_validate_raises_with_all_violations() -> None:
    """``validate`` raises carrying every broken rule."""
    with pytest.raises(WeakPasswordError) as error_info:
        PasswordPolicy().validate("short", EMAIL)
    assert len(error_info.value.violations) == 2
    assert error_info.value.code == "weak_password"


def test_validate_accepts_strong_password() -> None:
    """``validate`` returns silently for a valid password."""
    PasswordPolicy().validate("NovaSenha2026", EMAIL)
