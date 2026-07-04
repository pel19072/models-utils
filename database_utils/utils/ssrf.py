"""Shared SSRF guard for outbound HTTP made on behalf of stored Integrations.

Both the interactive "test integration" endpoint (backend-erp) and the automatic
workflow HTTP_REQUEST step (workflow_engine) send requests to an operator-supplied
`base_url` with stored credentials attached. Without validation that is an SSRF
primitive (cloud metadata 169.254.169.254, localhost, internal services) plus an
exfiltration channel. This module centralises the blocklist so every outbound
path uses the same guard (SEC-6).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFValidationError(Exception):
    """Raised when a URL resolves to a blocked / private / internal address."""


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_BLOCKED_KEYWORDS = ("localhost", "metadata", "internal")


def validate_url_no_ssrf(url: str) -> str:
    """Validate that `url`'s host is public and return the resolved IP.

    Rejects hostnames containing internal keywords and any host that resolves to a
    private/loopback/link-local address (checking ALL A/AAAA records to cover
    round-robin DNS). Returns the first validated IP so the caller may pin to it.
    Raises SSRFValidationError on any violation.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("Invalid URL: missing hostname")
    if any(kw in hostname.lower() for kw in _BLOCKED_KEYWORDS):
        raise SSRFValidationError("Requests to internal addresses are not allowed")
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SSRFValidationError("Could not resolve hostname") from exc
    if not infos:
        raise SSRFValidationError("Could not resolve hostname")
    for *_rest, sockaddr in (info[:] for info in infos):
        resolved_ip = ipaddress.ip_address(sockaddr[0])
        if any(resolved_ip in net for net in _PRIVATE_NETWORKS):
            raise SSRFValidationError("Requests to private network addresses are not allowed")
    return infos[0][4][0]
