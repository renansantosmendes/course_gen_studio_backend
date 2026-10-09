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
from coursegen_backend.presentation.api.routers import auth, health, password

API_PREFIX = "/api/v1"

API_DESCRIPTION = """
Authentication and password management API of **CourseGen Studio**
(SynapseAI Solutions).

## How authentication works

1. **Sign in** with `POST /api/v1/auth/login`. The response carries an
   `access_token`, a `refresh_token` and the user profile.
2. Send the access token in every authenticated request:
   `Authorization: Bearer <access_token>`. In this page, click
   **Authorize** and paste the token.
3. The access token is short-lived (15 minutes by default). When a request
   answers `401`, call `POST /api/v1/auth/refresh` with the refresh token.
   Each refresh **returns a new refresh token and invalidates the previous
   one**, so always store the latest.
4. **Sign out** with `POST /api/v1/auth/logout`. The session ends at once,
   on the server side.

## Password management

- **Forgot password**: `POST /api/v1/auth/password/forgot` e-mails a
  single-use link `<PASSWORD_RESET_URL>#reset_token=<token>`. The answer is
  the same whether or not the e-mail is registered.
- **Reset password**: `POST /api/v1/auth/password/reset` with that token
  defines the new password and ends every session of the user.
- **Change password**: `POST /api/v1/auth/password/change` (authenticated)
  requires the current password and ends the other sessions of the user.

New passwords must have 10 to 128 characters, at least one letter and one
digit, no leading or trailing whitespace, and must not contain the part of
the e-mail before the `@`.

## Errors

Every error answers with the same body:

```json
{"code": "invalid_credentials", "message": "Invalid e-mail or password."}
```

`code` is stable and meant for client logic; `message` is for humans.
Some errors include `details`, such as each broken password rule.

| Status | Codes |
|--------|-------|
| 400 | `invalid_password_reset_token`, `weak_password`, `password_reuse`, `incorrect_current_password` |
| 401 | `invalid_credentials`, `invalid_access_token`, `invalid_refresh_token` |
| 422 | `validation_error` |
| 429 | `too_many_login_attempts` (see the `Retry-After` header) |
| 500 | `internal_error` |
"""

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "Sign in, renew and end sessions, and read the "
        "authenticated user.",
    },
    {
        "name": "Password management",
        "description": "Recover a forgotten password by e-mail or change "
        "the current one.",
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
        summary="Sign-in, session and password management for CourseGen "
        "Studio.",
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
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(password.router, prefix=API_PREFIX)

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
