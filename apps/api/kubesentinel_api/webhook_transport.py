"""Operator-configured, IP-pinned webhooks: no DNS rebinding, redirects or proxies."""

import hashlib
import hmac
import http.client
import ipaddress
import re
import socket
import ssl
import threading
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Destination:
    host: str
    ip: str
    port: int
    path: str
    tls: bool


def validate_destination(url: str, address: str, local_http: bool = False) -> Destination:
    try:
        parsed = urlsplit(url)
        ip = ipaddress.ip_address(address)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise ValueError("Invalid escalation destination") from None
    host = parsed.hostname or ""
    if (
        parsed.scheme not in {"https", "http"}
        or not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", host)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(ord(c) < 33 or ord(c) > 126 for c in url)
        or "\\" in url
    ):
        raise ValueError("Escalation requires a configured HTTPS URL without credentials or query")
    lab = local_http and host == "127.0.0.1" and address == "127.0.0.1"
    if not lab and (parsed.scheme != "https" or port != 443 or not ip.is_global):
        raise ValueError("Escalation requires HTTPS port 443 and a public pinned IP")
    # Keep the first delivery implementation IPv4-only, excluding IPv6 translation/tunnel
    # forms that can route a seemingly global address to a private IPv4 target.
    if not isinstance(ip, ipaddress.IPv4Address):
        raise ValueError("Escalation currently requires an IPv4 pin")
    return Destination(host, address, port, parsed.path or "/", parsed.scheme == "https")


def signature(secret: str, timestamp: str, body: bytes) -> str:
    return (
        "sha256="
        + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    )


def deliver(
    destination: Destination,
    body: bytes,
    event_id: str,
    secret: str,
    timestamp: str,
    timeout: float,
) -> int:
    # Connect to the numeric configured address; never resolve the hostname a second time.
    # TLS still verifies the certificate and SNI against the original configured hostname.
    connection = http.client.HTTPConnection(destination.host, destination.port, timeout=timeout)
    deadline: threading.Timer | None = None

    def interrupt() -> None:
        # A receiver sending one header byte before each socket timeout must not
        # monopolize a worker indefinitely or outlive its durable delivery lease.
        sock = connection.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    try:
        connection.sock = socket.create_connection((destination.ip, destination.port), timeout)
        deadline = threading.Timer(timeout, interrupt)
        deadline.daemon = True
        deadline.start()
        if destination.tls:
            connection.sock = ssl.create_default_context().wrap_socket(
                connection.sock, server_hostname=destination.host
            )
        connection.request(
            "POST",
            destination.path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "KubeSentinel-Escalation/1",
                "X-KubeSentinel-Event-ID": event_id,
                "X-KubeSentinel-Timestamp": timestamp,
                "X-KubeSentinel-Signature": signature(secret, timestamp, body),
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        # Do not consume/store untrusted response bodies or follow redirects.
        return response.status
    finally:
        if deadline is not None:
            deadline.cancel()
        connection.close()
