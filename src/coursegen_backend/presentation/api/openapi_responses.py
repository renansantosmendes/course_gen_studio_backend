"""Error response descriptions reused by several routes."""

from coursegen_backend.presentation.api.error_handlers import (
    error_response_doc,
)

UNAUTHENTICATED_RESPONSE = error_response_doc(
    "The `Authorization: Bearer <access_token>` header is missing, or the "
    "token is invalid, expired or belongs to an ended session "
    "(`invalid_access_token`). Refresh the session or sign in again."
)

VALIDATION_RESPONSE = error_response_doc(
    "The request body is malformed (`validation_error`); `details` lists "
    "each invalid field."
)
