"""End-to-end tests of the HTTP API over in-memory adapters."""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from coursegen_backend.infrastructure.config import Settings
from coursegen_backend.presentation.api import dependencies
from coursegen_backend.presentation.api.app import create_app
from tests.conftest import TEST_JWT_SECRET
from tests.fakes import (
    FakeClock,
    FakePasswordHasher,
    InMemoryUnitOfWork,
    RecordingEmailSender,
    make_membership,
    make_user,
)

API = "/api/v1"
PASSWORD = "Planejamento2026"


@dataclass
class ApiHarness:
    """Test client together with the in-memory state behind it.

    Attributes
    ----------
    client : TestClient
        HTTP client of the application.
    unit_of_work : InMemoryUnitOfWork
        Storage used by the application.
    email_sender : RecordingEmailSender
        Collects the e-mails sent.
    """

    client: TestClient
    unit_of_work: InMemoryUnitOfWork
    email_sender: RecordingEmailSender


@pytest.fixture
def harness(
    unit_of_work: InMemoryUnitOfWork,
    clock: FakeClock,
) -> ApiHarness:
    """Build the application with every adapter replaced by a fake.

    Parameters
    ----------
    unit_of_work : InMemoryUnitOfWork
        In-memory unit of work.
    clock : FakeClock
        Frozen clock.

    Returns
    -------
    ApiHarness
        Client and in-memory state.
    """
    settings = Settings(
        _env_file=None,
        COURSEGEN_DATABASE_URL="postgresql://unused/test",
        COURSEGEN_JWT_SECRET_KEY=TEST_JWT_SECRET,
        password_reset_url="https://app.edu/coursegen-login.html",
        cors_allowed_origins="https://app.edu",
        login_max_failed_attempts=2,
    )
    email_sender = RecordingEmailSender()
    password_hasher = FakePasswordHasher()
    app = create_app(settings)
    app.dependency_overrides.update(
        {
            dependencies.get_app_settings: lambda: settings,
            dependencies.get_unit_of_work: lambda: unit_of_work,
            dependencies.get_password_hasher: lambda: password_hasher,
            dependencies.get_email_sender: lambda: email_sender,
            dependencies.get_clock: lambda: clock,
        }
    )
    unit_of_work.users.add(make_user(), [make_membership()])
    return ApiHarness(
        client=TestClient(app),
        unit_of_work=unit_of_work,
        email_sender=email_sender,
    )


def login(
    harness: ApiHarness,
    password: str = PASSWORD,
) -> dict:
    """Call the sign-in endpoint.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.
    password : str
        Password to send.

    Returns
    -------
    dict
        JSON body of the response, including ``status_code``.
    """
    response = harness.client.post(
        f"{API}/auth/login",
        json={
            "email": "camila.torres@instituicao.edu.br",
            "password": password,
            "keep_signed_in": True,
        },
        headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
    )
    return {"status_code": response.status_code, **response.json()}


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


def test_health_and_root_redirect(harness: ApiHarness) -> None:
    """Health answers ok and the root redirects to the docs.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    assert harness.client.get(f"{API}/health").json()["status"] == "ok"
    response = harness.client.get("/", follow_redirects=False)
    assert response.headers["location"] == "/docs"


def test_login_me_refresh_logout_flow(harness: ApiHarness) -> None:
    """The full session life cycle works through HTTP.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    body = login(harness)
    assert body["status_code"] == 200
    assert body["token_type"] == "bearer"
    assert 0 < body["expires_in"] <= 900
    assert body["user"]["organizations"][0]["roles"] == ["author", "reviewer"]
    session = next(iter(harness.unit_of_work.sessions.sessions.values()))
    assert session.keep_signed_in
    me = harness.client.get(
        f"{API}/auth/me",
        headers=bearer(body["access_token"]),
    )
    assert me.status_code == 200
    assert me.json()["email"] == "camila.torres@instituicao.edu.br"
    refreshed = harness.client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert refreshed.status_code == 200
    reused = harness.client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["code"] == "invalid_refresh_token"
    new_access_token = refreshed.json()["access_token"]
    logout = harness.client.post(
        f"{API}/auth/logout",
        headers=bearer(new_access_token),
    )
    assert logout.status_code == 204
    after = harness.client.get(
        f"{API}/auth/me",
        headers=bearer(new_access_token),
    )
    assert after.status_code == 401
    assert after.headers["www-authenticate"] == "Bearer"


def test_login_failures_and_throttle(harness: ApiHarness) -> None:
    """Wrong passwords answer 401 and then 429 with ``Retry-After``.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    for _ in range(2):
        failed = login(harness, password="wrong-password1")
        assert failed["status_code"] == 401
        assert failed["code"] == "invalid_credentials"
    event, _ = harness.unit_of_work.audit_log.entries[0]
    assert event.ip_address == "203.0.113.7"
    response = harness.client.post(
        f"{API}/auth/login",
        json={
            "email": "camila.torres@instituicao.edu.br",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"


def test_validation_errors_use_error_body(harness: ApiHarness) -> None:
    """Malformed bodies answer 422 with ``validation_error``.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    response = harness.client.post(
        f"{API}/auth/login",
        json={"email": "not-an-email", "password": ""},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert any("email" in detail for detail in response.json()["details"])


def test_protected_routes_require_token(harness: ApiHarness) -> None:
    """Missing or bad tokens answer 401 ``invalid_access_token``.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    assert harness.client.get(f"{API}/auth/me").status_code == 401
    response = harness.client.post(
        f"{API}/auth/password/change",
        json={"current_password": "a", "new_password": "b"},
        headers=bearer("garbage"),
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_access_token"


def test_forgot_and_reset_password_flow(harness: ApiHarness) -> None:
    """Recovery is neutral, e-mails a link and resets the password.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    unknown = harness.client.post(
        f"{API}/auth/password/forgot",
        json={"email": "nobody@uni.edu"},
    )
    known = harness.client.post(
        f"{API}/auth/password/forgot",
        json={"email": "camila.torres@instituicao.edu.br"},
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(harness.email_sender.messages) == 1
    body = harness.email_sender.messages[0].body
    token = body.split("#reset_token=", 1)[1].split()[0]
    weak = harness.client.post(
        f"{API}/auth/password/reset",
        json={"reset_token": token, "new_password": "fraca"},
    )
    assert weak.status_code == 400
    assert weak.json()["code"] == "weak_password"
    assert weak.json()["details"]
    reset = harness.client.post(
        f"{API}/auth/password/reset",
        json={"reset_token": token, "new_password": "NovaSenhaSegura2026"},
    )
    assert reset.status_code == 204
    assert login(harness, password="NovaSenhaSegura2026")["status_code"] == 200


def test_change_password(harness: ApiHarness) -> None:
    """An authenticated user changes the password and keeps the session.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    access_token = login(harness)["access_token"]
    wrong = harness.client.post(
        f"{API}/auth/password/change",
        json={
            "current_password": "wrong-password1",
            "new_password": "NovaSenhaSegura2026",
        },
        headers=bearer(access_token),
    )
    assert wrong.json()["code"] == "incorrect_current_password"
    changed = harness.client.post(
        f"{API}/auth/password/change",
        json={
            "current_password": PASSWORD,
            "new_password": "NovaSenhaSegura2026",
        },
        headers=bearer(access_token),
    )
    assert changed.status_code == 204
    me = harness.client.get(f"{API}/auth/me", headers=bearer(access_token))
    assert me.status_code == 200


def test_cors_preflight_allows_configured_origin(harness: ApiHarness) -> None:
    """The configured front-end origin passes the CORS preflight.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    response = harness.client.options(
        f"{API}/auth/login",
        headers={
            "Origin": "https://app.edu",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == (
        "https://app.edu"
    )


def test_openapi_documents_every_route(harness: ApiHarness) -> None:
    """Every route has a summary, a description and error models.

    Parameters
    ----------
    harness : ApiHarness
        Test harness.

    Returns
    -------
    None
    """
    spec = harness.client.get("/openapi.json").json()
    for path, operations in spec["paths"].items():
        for operation in operations.values():
            assert operation["summary"], path
            assert operation["description"], path
    me_operation = spec["paths"][f"{API}/auth/me"]["get"]
    assert me_operation["security"] == [{"BearerAuth": []}]
    assert "ErrorResponse" in spec["components"]["schemas"]
