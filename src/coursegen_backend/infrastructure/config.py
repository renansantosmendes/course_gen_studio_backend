"""Application settings, read from environment variables or ``.env``."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration of the API.

    Every attribute maps to the environment variable of the same name in
    upper case (for example, ``database_url`` comes from
    ``COURSEGEN_DATABASE_URL`` through its alias).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "production"] = "development"
    database_url: SecretStr = Field(alias="COURSEGEN_DATABASE_URL")
    jwt_secret_key: SecretStr = Field(alias="COURSEGEN_JWT_SECRET_KEY")
    jwt_issuer: str = "coursegen-studio"
    access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_hours: int = Field(default=12, gt=0)
    keep_signed_in_ttl_days: int = Field(default=30, gt=0)
    password_reset_ttl_minutes: int = Field(default=30, gt=0)
    password_reset_url: str = (
        "http://localhost:5500/coursegen-login.html"
    )
    login_max_failed_attempts: int = Field(default=5, gt=0)
    login_throttle_window_minutes: int = Field(default=15, gt=0)
    cors_allowed_origins: str = ""
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_sender: str | None = None
    smtp_use_tls: bool = True

    @property
    def cors_origins(self) -> list[str]:
        """Split the comma-separated list of allowed CORS origins.

        Returns
        -------
        list[str]
            Allowed origins, without blanks.
        """
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Load the settings once per process.

    Returns
    -------
    Settings
        Cached settings instance.
    """
    return Settings()
