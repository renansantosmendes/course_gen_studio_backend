"""FastAPI application factory."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from coursegen_backend import __version__
from coursegen_backend.infrastructure.config import Settings, get_settings
from coursegen_backend.presentation.api.error_handlers import (
    register_error_handlers,
)
from coursegen_backend.presentation.api.routers import health, me

API_PREFIX = "/api/v1"

API_DESCRIPTION = """
API of **CourseGen Studio** (SynapseAI Solutions).

## Authentication

CourseGen does not sign users in itself: accounts, sessions and passwords
live in the shared **auth service**. The front end signs in there
(`POST /api/v1/auth/login`), renews the session there
(`POST /api/v1/auth/refresh`) and sends the access token it receives to
this API as `Authorization: Bearer <access_token>`. In this page, click
**Authorize** and paste the token.

This API verifies each token with the auth service's public keys (RS256,
`AUTH_JWKS_URL`), checking issuer and audience. The first request of an
account creates its CourseGen profile with the token's identifier, e-mail
and name.

## Errors

Every error answers with the same body:

```json
{"code": "invalid_access_token", "message": "The access token is missing, invalid or expired."}
```

`code` is stable and meant for client logic; `message` is for humans.

| Status | Codes |
|--------|-------|
| 401 | `invalid_access_token` |
| 403 | `account_disabled` |
| 409 | `account_link_conflict` |
| 422 | `validation_error` |
| 500 | `internal_error` |
| 503 | `auth_service_unavailable` |
"""

OPENAPI_TAGS = [
    {
        "name": "Profile",
        "description": "The authenticated user's CourseGen profile, "
        "organizations and roles.",
    },
    {
        "name": "Health",
        "description": "Liveness check of the API.",
    },
]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application with routes, CORS and error handlers.

    Parameters
    ----------
    settings : Settings | None
        Settings used at start-up (CORS origins). When omitted, they are
        read from the environment.

    Returns
    -------
    FastAPI
        Configured application.

    Example
    -------
    >>> import uvicorn
    >>> uvicorn.run(create_app(), port=8000)
    """
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(
        title="CourseGen Studio API",
        version=__version__,
        summary="Course design back end of CourseGen Studio.",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        contact={
            "name": "SynapseAI Solutions",
            "url": "https://www.synapseai.com",
        },
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True,
        },
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["Retry-After"],
        )
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(me.router, prefix=API_PREFIX)

    @app.get("/", include_in_schema=False)
    def redirect_to_docs() -> RedirectResponse:
        """Send visitors of the root URL to the Swagger UI.

        Returns
        -------
        RedirectResponse
            Redirect to ``/docs``.
        """
        return RedirectResponse(url="/docs")

    return app
