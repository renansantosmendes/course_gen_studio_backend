"""Request and response bodies of the authentication endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from coursegen_backend.application.dto import SessionTokens, UserProfile


class LoginRequest(BaseModel):
    """Credentials informed on the sign-in screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "camila.torres@instituicao.edu.br",
                    "password": "Planejamento2026",
                    "keep_signed_in": True,
                }
            ]
        }
    )

    email: EmailStr = Field(
        description="Institutional e-mail of the account (case-insensitive).",
    )
    password: str = Field(
        min_length=1,
        max_length=256,
        description="Password of the account, in plain text.",
    )
    keep_signed_in: bool = Field(
        default=False,
        description=(
            "Matches the *Keep me signed in on this device* checkbox. When "
            "`true`, the refresh token lives for "
            "`KEEP_SIGNED_IN_TTL_DAYS` (default 30 days) instead of "
            "`REFRESH_TOKEN_TTL_HOURS` (default 12 hours)."
        ),
    )


class RefreshRequest(BaseModel):
    """Refresh token to exchange for new credentials."""

    refresh_token: str = Field(
        min_length=1,
        max_length=512,
        description=(
            "Refresh token received from `POST /auth/login` or from the "
            "previous `POST /auth/refresh`."
        ),
        examples=["q3V1c2VyLXJlZnJlc2gtdG9rZW4tZXhhbXBsZQ"],
    )


class TokenResponse(BaseModel):
    """Credentials of a session."""

    access_token: str = Field(
        description=(
            "Short-lived JWT. Send it in the `Authorization: Bearer "
            "<access_token>` header of authenticated requests."
        ),
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Authentication scheme of the access token.",
    )
    expires_in: int = Field(
        description="Seconds until the access token expires.",
        examples=[900],
    )
    access_token_expires_at: datetime = Field(
        description="Expiration moment of the access token (UTC).",
    )
    refresh_token: str = Field(
        description=(
            "Opaque token used once in `POST /auth/refresh` to obtain new "
            "credentials. Store it securely; each refresh returns a new "
            "one and invalidates the previous."
        ),
        examples=["q3V1c2VyLXJlZnJlc2gtdG9rZW4tZXhhbXBsZQ"],
    )
    refresh_token_expires_at: datetime = Field(
        description="Expiration moment of the refresh token (UTC).",
    )

    @classmethod
    def from_session_tokens(
        cls,
        tokens: SessionTokens,
        issued_at: datetime,
    ) -> "TokenResponse":
        """Build the response from the session credentials.

        Parameters
        ----------
        tokens : SessionTokens
            Credentials returned by a use case.
        issued_at : datetime
            Current moment, used to compute ``expires_in``.

        Returns
        -------
        TokenResponse
            The response body.
        """
        return cls(
            access_token=tokens.access_token,
            expires_in=max(
                0,
                int(
                    (
                        tokens.access_token_expires_at - issued_at
                    ).total_seconds()
                ),
            ),
            access_token_expires_at=tokens.access_token_expires_at,
            refresh_token=tokens.refresh_token,
            refresh_token_expires_at=tokens.refresh_token_expires_at,
        )


class OrganizationMembershipResponse(BaseModel):
    """An organization of the user and the roles held in it."""

    id: UUID = Field(description="Identifier of the organization.")
    name: str = Field(
        description="Display name of the organization.",
        examples=["Universidade Exemplo"],
    )
    slug: str = Field(
        description="URL-friendly unique name of the organization.",
        examples=["universidade-exemplo"],
    )
    roles: list[Literal["author", "reviewer", "curator", "admin"]] = Field(
        description="Roles of the user in this organization.",
        examples=[["author", "reviewer"]],
    )


class UserResponse(BaseModel):
    """Profile of a user."""

    id: UUID = Field(description="Identifier of the user.")
    email: EmailStr = Field(
        description="Institutional e-mail.",
        examples=["camila.torres@instituicao.edu.br"],
    )
    full_name: str = Field(
        description="Name displayed in the interface.",
        examples=["Camila Torres"],
    )
    job_title: str | None = Field(
        description="Job title, when informed.",
        examples=["Instructional designer"],
    )
    last_login_at: datetime | None = Field(
        description=(
            "Moment of the last successful sign-in (UTC). In the login "
            "response it already reflects the current sign-in."
        ),
    )
    organizations: list[OrganizationMembershipResponse] = Field(
        description="Organizations (tenants) the user belongs to.",
    )

    @classmethod
    def from_profile(
        cls,
        profile: UserProfile,
    ) -> "UserResponse":
        """Build the response from a user profile.

        Parameters
        ----------
        profile : UserProfile
            Profile returned by a use case.

        Returns
        -------
        UserResponse
            The response body.
        """
        user = profile.user
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            job_title=user.job_title,
            last_login_at=user.last_login_at,
            organizations=[
                OrganizationMembershipResponse(
                    id=membership.organization_id,
                    name=membership.organization_name,
                    slug=membership.organization_slug,
                    roles=list(membership.roles),
                )
                for membership in profile.memberships
            ],
        )


class LoginResponse(TokenResponse):
    """Credentials of the new session and the signed-in user."""

    user: UserResponse = Field(description="The signed-in user.")
