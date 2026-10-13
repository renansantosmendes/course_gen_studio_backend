"""Error response descriptions reused by several routes."""

from coursegen_backend.presentation.api.error_handlers import (
    error_response_doc,
)

UNAUTHENTICATED_RESPONSE = error_response_doc(
    "The `Authorization: Bearer <access_token>` header is missing, or the "
    "token is invalid, expired or was not issued by the auth service for "
    "this audience (`invalid_access_token`). Refresh the session in the "
    "auth service or sign in again."
)

ACCOUNT_DISABLED_RESPONSE = error_response_doc(
    "The person was blocked from CourseGen Studio by an administrator "
    "(`account_disabled`), even though the auth service account is valid."
)

ACCOUNT_LINK_CONFLICT_RESPONSE = error_response_doc(
    "Another CourseGen profile already uses this e-mail "
    "(`account_link_conflict`); an administrator must resolve it."
)

AUTH_SERVICE_UNAVAILABLE_RESPONSE = error_response_doc(
    "The public keys of the auth service could not be fetched "
    "(`auth_service_unavailable`). Retry later."
)
