"""Application settings, read from environment variables or ``.env``."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration of the API.

    Every attribute maps to the environment variable of the same name in
    upper case, except those with an explicit alias (for example,
    ``database_url`` comes from ``COURSEGEN_DATABASE_URL``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "production"] = "development"
    database_url: SecretStr = Field(alias="COURSEGEN_DATABASE_URL")
    auth_jwks_url: str = Field(alias="AUTH_JWKS_URL")
    auth_issuer: str = Field(default="auth-service", alias="AUTH_JWT_ISSUER")
    auth_audience: str = Field(
        default="synapse-apps",
        alias="AUTH_JWT_AUDIENCE",
    )
    cors_allowed_origins: str = ""

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
