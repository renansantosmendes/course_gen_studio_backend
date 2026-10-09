"""Liveness endpoint used by monitors and deploy checks."""

from fastapi import APIRouter

from coursegen_backend import __version__
from coursegen_backend.presentation.api.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check that the API is running",
    description=(
        "Answers `200` whenever the API process is up. It does not touch "
        "the database, so it is cheap enough for frequent monitoring."
    ),
    response_description="The API is running.",
)
def health() -> HealthResponse:
    """Report that the API is alive.

    Returns
    -------
    HealthResponse
        Status and version of the API.
    """
    return HealthResponse(status="ok", version=__version__)
