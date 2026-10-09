"""Tests of the application settings."""

import pytest
from pydantic import ValidationError

from coursegen_backend.infrastructure.config import Settings


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
    monkeypatch.setenv("COURSEGEN_DATABASE_URL", "postgresql://db/test")
    monkeypatch.setenv("COURSEGEN_JWT_SECRET_KEY", "s3cr3t-value-xyz")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://a.edu, ,https://b.edu",
    )
    settings = Settings(_env_file=None)
    assert settings.database_url.get_secret_value() == "postgresql://db/test"
    assert settings.access_token_ttl_minutes == 15
    assert settings.cors_origins == ["https://a.edu", "https://b.edu"]
    assert "s3cr3t-value-xyz" not in repr(settings)


def test_settings_require_database_and_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing mandatory variables fail at start-up.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Removes environment variables.

    Returns
    -------
    None
    """
    monkeypatch.delenv("COURSEGEN_DATABASE_URL", raising=False)
    monkeypatch.delenv("COURSEGEN_JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
