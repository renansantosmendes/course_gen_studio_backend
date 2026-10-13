"""Response bodies shared by every endpoint."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Body returned by every error response of the API."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "validation_error",
                    "message": "The request body or parameters are invalid.",
                    "details": ["query.limit: Input should be a valid integer"],
                }
            ]
        }
    )

    code: str = Field(
        description=(
            "Stable, machine-readable error identifier. Client code should "
            "branch on this value, never on `message`."
        ),
        examples=["invalid_access_token"],
    )
    message: str = Field(
        description="Human-readable explanation of the error, in English.",
        examples=["The access token is missing, invalid or expired."],
    )
    details: list[str] | None = Field(
        default=None,
        description=(
            "Additional explanations, such as each invalid request field. "
            "Omitted when not applicable."
        ),
    )


class MessageResponse(BaseModel):
    """Generic confirmation message."""

    message: str = Field(
        description="Human-readable confirmation, in English.",
        examples=["Operation completed."],
    )


class HealthResponse(BaseModel):
    """Liveness information of the API."""

    status: str = Field(
        description="Always `ok` when the API is able to answer.",
        examples=["ok"],
    )
    version: str = Field(
        description="Version of the deployed API.",
        examples=["1.0.0"],
    )
