"""Response bodies of the profile endpoint."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from coursegen_backend.application.dto import UserProfile


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


class UserProfileResponse(BaseModel):
    """CourseGen Studio profile of the authenticated user."""

    id: UUID = Field(
        description=(
            "Identifier of the user; the same as the account in the auth "
            "service (the token's `sub` claim)."
        ),
    )
    email: EmailStr = Field(
        description="E-mail, kept in sync with the auth service.",
        examples=["camila.torres@example.com"],
    )
    full_name: str = Field(
        description="Name, kept in sync with the auth service.",
        examples=["Camila Torres"],
    )
    job_title: str | None = Field(
        description="Job title in CourseGen Studio, when informed.",
        examples=["Instructional designer"],
    )
    organizations: list[OrganizationMembershipResponse] = Field(
        description="Organizations (tenants) the user belongs to.",
    )

    @classmethod
    def from_profile(
        cls,
        profile: UserProfile,
    ) -> "UserProfileResponse":
        """Build the response from a user profile.

        Parameters
        ----------
        profile : UserProfile
            Profile returned by a use case.

        Returns
        -------
        UserProfileResponse
            The response body.
        """
        user = profile.user
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            job_title=user.job_title,
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
