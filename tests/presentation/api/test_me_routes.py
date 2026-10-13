"""End-to-end tests of the HTTP API over in-memory adapters."""

import pytest
from fastapi.testclient import TestClient

from coursegen_backend.domain.exceptions import AuthServiceUnavailableError
from coursegen_backend.infrastructure.config import Settings
from coursegen_backend.infrastructure.security.jwks_access_token_verifier import (
    JwksAccessTokenVerifier,
)
from coursegen_backend.presentation.api import dependencies
from coursegen_backend.presentation.api.app import create_app
from tests.conftest import AUDIENCE, ISSUER, issue_token
from tests.fakes import (
    InMemoryUnitOfWork,
    make_identity,
    make_membership,
    make_user,
)

ME = "/api/v1/me"


def build_client(
    unit_of_work: InMemoryUnitOfWork,
    access_token_verifier: JwksAccessTokenVerifier,
) -> TestClient:
    """Build the application with every adapter replaced by a fake.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    access_token_verifier : JwksAccessTokenVerifier
        Verifier trusting the test key.

    Returns
    -------
    TestClient
        HTTP client of the application.
    """
    settings = Settings(
        _env_file=None,
        COURSEGEN_DATABASE_URL="postgresql://unused/test",
        AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        cors_allowed_origins="https://app.edu",
    )
    app = create_app(settings)
    app.dependency_overrides.update(
        {
            dependencies.get_app_settings: lambda: settings,
            dependencies.get_unit_of_work: lambda: unit_of_work,
            dependencies.get_access_token_verifier: lambda: access_token_verifier,
        }
    )
    return TestClient(app)


@pytest.fixture
def client(
    unit_of_work: InMemoryUnitOfWork,
    access_token_verifier: JwksAccessTokenVerifier,
) -> TestClient:
    """Provide the HTTP client over in-memory adapters.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    access_token_verifier : JwksAccessTokenVerifier
        Verifier trusting the test key.

    Returns
    -------
    TestClient
        HTTP client of the application.
    """
    return build_client(unit_of_work, access_token_verifier)


def bearer(token: str) -> dict[str, str]:
    """Build the authorization header.

    Parameters
    ----------
    token : str
        Access token.

    Returns
    -------
    dict[str, str]
        Header dictionary.
    """
    return {"Authorization": f"Bearer {token}"}


def test_health_and_root_redirect(client: TestClient) -> None:
    """Health answers ok and the root redirects to the docs.

    Parameters
    ----------
    client : TestClient
        HTTP client.

    Returns
    -------
    None
    """
    assert client.get("/api/v1/health").json()["status"] == "ok"
    response = client.get("/", follow_redirects=False)
    assert response.headers["location"] == "/docs"


def test_me_provisions_and_returns_profile(
    client: TestClient,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """The first call with an auth service token creates the profile.

    Parameters
    ----------
    client : TestClient
        HTTP client.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    response = client.get(ME, headers=bearer(issue_token(identity)))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(identity.user_id)
    assert body["email"] == identity.email
    assert body["organizations"] == []
    assert identity.user_id in unit_of_work.users.users


def test_me_lists_organizations(
    client: TestClient,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """Existing profiles return their organizations and roles.

    Parameters
    ----------
    client : TestClient
        HTTP client.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    unit_of_work.users.add(make_user(identity), [make_membership()])
    body = client.get(ME, headers=bearer(issue_token(identity))).json()
    assert body["job_title"] == "Instructional designer"
    assert body["organizations"][0]["roles"] == ["author", "reviewer"]


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer not-a-jwt"},
        bearer(issue_token(make_identity(), aud="other-app")),
    ],
)
def test_me_requires_a_trusted_token(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    """Missing, malformed or foreign tokens answer 401.

    Parameters
    ----------
    client : TestClient
        HTTP client.
    headers : dict[str, str]
        Request headers.

    Returns
    -------
    None
    """
    response = client.get(ME, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_access_token"
    assert response.headers["www-authenticate"] == "Bearer"


def test_disabled_profile_answers_403(
    client: TestClient,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A CourseGen block wins over a valid token.

    Parameters
    ----------
    client : TestClient
        HTTP client.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    identity = make_identity()
    unit_of_work.users.add(make_user(identity, is_active=False))
    response = client.get(ME, headers=bearer(issue_token(identity)))
    assert response.status_code == 403
    assert response.json()["code"] == "account_disabled"


def test_email_conflict_answers_409(
    client: TestClient,
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """A legacy profile with the same e-mail answers 409.

    Parameters
    ----------
    client : TestClient
        HTTP client.
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """
    unit_of_work.users.add(make_user(make_identity()))
    response = client.get(ME, headers=bearer(issue_token(make_identity())))
    assert response.status_code == 409
    assert response.json()["code"] == "account_link_conflict"


def test_unreachable_auth_service_answers_503(
    unit_of_work: InMemoryUnitOfWork,
) -> None:
    """Failing to fetch the public keys is reported as 503.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.

    Returns
    -------
    None
    """

    def unreachable(_token: str) -> None:
        """Simulate an unreachable JWKS endpoint.

        Parameters
        ----------
        _token : str
            Token being verified.

        Returns
        -------
        None
        """
        raise AuthServiceUnavailableError()

    verifier = JwksAccessTokenVerifier(
        signing_key_resolver=unreachable,
        issuer=ISSUER,
        audience=AUDIENCE,
    )
    response = build_client(unit_of_work, verifier).get(
        ME,
        headers=bearer(issue_token(make_identity())),
    )
    assert response.status_code == 503
    assert response.json()["code"] == "auth_service_unavailable"


def test_login_routes_moved_to_auth_service(client: TestClient) -> None:
    """The old login and password routes no longer exist here.

    Parameters
    ----------
    client : TestClient
        HTTP client.

    Returns
    -------
    None
    """
    assert client.post("/api/v1/auth/login", json={}).status_code == 404
    assert client.post("/api/v1/auth/password/forgot", json={}).status_code == 404


def test_openapi_documents_every_route(client: TestClient) -> None:
    """Every route has a summary, a description and the bearer scheme.

    Parameters
    ----------
    client : TestClient
        HTTP client.

    Returns
    -------
    None
    """
    spec = client.get("/openapi.json").json()
    for path, operations in spec["paths"].items():
        for operation in operations.values():
            assert operation["summary"], path
            assert operation["description"], path
    me_operation = spec["paths"][ME]["get"]
    assert me_operation["security"] == [{"BearerAuth": []}]
    assert {"401", "403", "409", "503"} <= set(me_operation["responses"])
