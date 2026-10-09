"""Extraction of client information from HTTP requests."""

import ipaddress

from fastapi import Request

from coursegen_backend.application.dto import RequestContext

MAX_USER_AGENT_LENGTH = 512


def parse_ip_address(raw_value: str | None) -> str | None:
    """Validate an IP address, discarding anything that is not one.

    Parameters
    ----------
    raw_value : str | None
        Candidate address, possibly surrounded by whitespace.

    Returns
    -------
    str | None
        The normalized address, or ``None`` when it is not valid.
    """
    if not raw_value:
        return None
    try:
        return str(ipaddress.ip_address(raw_value.strip()))
    except ValueError:
        return None


def extract_client_ip(request: Request) -> str | None:
    """Find the IP address of the client behind the Vercel proxy.

    Vercel sets ``X-Forwarded-For`` and ``X-Real-IP`` with the real
    client address; outside a proxy, the socket peer address is used.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    str | None
        The client address, or ``None`` when it cannot be determined.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        address = parse_ip_address(forwarded_for.split(",", 1)[0])
        if address:
            return address
    address = parse_ip_address(request.headers.get("x-real-ip"))
    if address:
        return address
    return parse_ip_address(request.client.host if request.client else None)


def build_request_context(request: Request) -> RequestContext:
    """Collect the client information used by the use cases.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    RequestContext
        IP address and user agent of the client.
    """
    user_agent = request.headers.get("user-agent")
    return RequestContext(
        ip_address=extract_client_ip(request),
        user_agent=user_agent[:MAX_USER_AGENT_LENGTH] if user_agent else None,
    )
