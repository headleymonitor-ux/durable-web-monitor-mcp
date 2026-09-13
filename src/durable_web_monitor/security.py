"""Network-target validation for public HTTPS monitoring."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeTarget(ValueError):
    """Raised when a target is outside the public HTTPS policy."""


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_https_url(url: str) -> str:
    """Validate a public HTTPS URL and return its hostname.

    This is a defense-in-depth application check, not a complete SSRF sandbox.
    """
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise UnsafeTarget("only https:// targets are allowed")
    if not parts.hostname:
        raise UnsafeTarget("target must include a hostname")
    if parts.username is not None or parts.password is not None:
        raise UnsafeTarget("embedded credentials are not allowed")
    if parts.port not in (None, 443):
        raise UnsafeTarget("only the default HTTPS port 443 is allowed")

    hostname = parts.hostname.rstrip(".")
    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeTarget(f"DNS resolution failed for {hostname}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeTarget("hostname resolved to no addresses")
    rejected = sorted(address for address in addresses if not _is_public_ip(address))
    if rejected:
        raise UnsafeTarget("target resolves to a non-public address")

    return hostname
