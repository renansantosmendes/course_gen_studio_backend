"""Tests of the client information extraction."""

from starlette.requests import Request

from coursegen_backend.presentation.api.request_context import (
    MAX_USER_AGENT_LENGTH,
    build_request_context,
    parse_ip_address,
)


def build_request(
    headers: dict[str, str],
    client_host: str | None = "198.51.100.1",
) -> Request:
    """Create a bare ASGI request.

    Parameters
    ----------
    headers : dict[str, str]
        Request headers.
    client_host : str | None
        Socket peer address.

    Returns
    -------
    Request
        Request object.
    """
    scope = {
        "type": "http",
        "headers": [
            (name.lower().encode(), value.encode())
            for name, value in headers.items()
        ],
        "client": (client_host, 1234) if client_host else None,
    }
    return Request(scope)


def test_parse_ip_address_rejects_garbage() -> None:
    """Only real IPv4 or IPv6 addresses are kept."""
    assert parse_ip_address(" 2001:db8::1 ") == "2001:db8::1"
    assert parse_ip_address("unknown") is None
    assert parse_ip_address(None) is None


def test_forwarded_for_takes_precedence() -> None:
    """The first ``X-Forwarded-For`` entry is the client."""
    context = build_request_context(
        build_request(
            {
                "X-Forwarded-For": "203.0.113.7, 10.0.0.1",
                "X-Real-IP": "192.0.2.9",
            }
        )
    )
    assert context.ip_address == "203.0.113.7"


def test_falls_back_to_real_ip_and_socket() -> None:
    """Without forwarding headers, later sources are used."""
    assert (
        build_request_context(
            build_request({"X-Real-IP": "192.0.2.9"})
        ).ip_address
        == "192.0.2.9"
    )
    assert build_request_context(build_request({})).ip_address == (
        "198.51.100.1"
    )
    assert build_request_context(
        build_request({}, client_host=None)
    ).ip_address is None


def test_user_agent_is_truncated() -> None:
    """Very long user agents are cut to the stored limit."""
    context = build_request_context(
        build_request({"User-Agent": "x" * 2000})
    )
    assert len(context.user_agent) == MAX_USER_AGENT_LENGTH
