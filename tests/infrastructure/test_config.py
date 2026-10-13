"""Tests of the application settings."""

import pytest
from pydantic import ValidationError

from coursegen_backend.infrastructure.config import Settings

DATABASE_URL = "postgresql://db/test"
JWKS_URL = "https://auth.example.com/.well-known/jwks.json"


def test_settings_read_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variables are read from the environment with defaults.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Sets environment variables.

    Returns
    -------
    None
    """
    monkeypatch.setenv("COURSEGEN_DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("AUTH_JWKS_URL", JWKS_URL)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://a.edu, ,https://b.edu",
    )
    settings = Settings(_env_file=None)
    assert settings.database_url.get_secret_value() == DATABASE_URL
    assert settings.auth_jwks_url == JWKS_URL
    assert settings.auth_issuer == "auth-service"
    assert settings.auth_audience == "synapse-apps"
    assert settings.cors_origins == ["https://a.edu", "https://b.edu"]
    assert DATABASE_URL not in repr(settings)


@pytest.mark.parametrize("missing", ["COURSEGEN_DATABASE_URL", "AUTH_JWKS_URL"])
def test_settings_require_database_and_jwks(
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    """Missing mandatory variables fail at start-up.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Sets and removes environment variables.
    missing : str
        Variable left out.

    Returns
    -------
    None
    """
    monkeypatch.setenv("COURSEGEN_DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("AUTH_JWKS_URL", JWKS_URL)
    monkeypatch.delenv(missing)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
