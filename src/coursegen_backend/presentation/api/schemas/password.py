"""Request bodies of the password management endpoints."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

PASSWORD_RULES = (
    "Must have 10 to 128 characters, at least one letter and one digit, "
    "no leading or trailing whitespace, and must not contain the part of "
    "the e-mail before the `@`."
)


class ForgotPasswordRequest(BaseModel):
    """E-mail of the account to recover."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "camila.torres@instituicao.edu.br"}]
        }
    )

    email: EmailStr = Field(
        description="Institutional e-mail informed on the recovery screen.",
    )


class ResetPasswordRequest(BaseModel):
    """Reset token from the recovery e-mail and the new password."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reset_token": "Zm9yZ290LXBhc3N3b3JkLXRva2VuLWV4YW1wbGU",
                    "new_password": "NovaSenhaSegura2026",
                }
            ]
        }
    )

    reset_token: str = Field(
        min_length=1,
        max_length=512,
        description=(
            "Token read from the `reset_token` parameter in the fragment "
            "of the link sent by e-mail (`...#reset_token=<token>`)."
        ),
    )
    new_password: str = Field(
        min_length=1,
        max_length=256,
        description=f"New password. {PASSWORD_RULES}",
    )


class ChangePasswordRequest(BaseModel):
    """Current and new password of the authenticated user."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "current_password": "Planejamento2026",
                    "new_password": "NovaSenhaSegura2026",
                }
            ]
        }
    )

    current_password: str = Field(
        min_length=1,
        max_length=256,
        description="Current password, to confirm the identity of the user.",
    )
    new_password: str = Field(
        min_length=1,
        max_length=256,
        description=(
            f"New password. {PASSWORD_RULES} Must differ from the current "
            "one."
        ),
    )
