"""SSRF guard for user-supplied stream URLs.

`/play <url>` lets any group member hand an arbitrary URL to yt-dlp and to the
bot's HTTP client. Without a check that reaches cloud metadata endpoints
(169.254.169.254, metadata.google.internal), loopback admin ports, and anything
else on the host's private network -- from a Telegram group, by anyone.

The check resolves the hostname and validates *every* address the resolver
returns, so a public name deliberately pointed at 127.0.0.1 is rejected too.
Only globally-routable unicast addresses are allowed.

Network consumers must use public_addresses at connection time and connect to
one of the returned IP literals. A preflight check alone does not prevent DNS
rebinding or redirects to a private address.
"""
import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Names that resolve to metadata services or the host itself. Checked before DNS
# so a broken/hostile resolver cannot help.
BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
    "instance-data.ec2.internal",
})

ALLOWED_SCHEMES = frozenset({"http", "https"})

DNS_TIMEOUT = 5.0


def _reject_reason(ip: ipaddress._BaseAddress) -> str | None:
    """Return why this address must not be fetched, or None when it is allowed.

    `is_global` is the primitive that matters: it is False for loopback, RFC1918
    private space, link-local (including the 169.254.169.254 metadata address),
    carrier-grade NAT, the unspecified address, and for IPv6 forms that embed a
    non-global IPv4 address (::ffff:, 2002::/16 6to4, Teredo). Multicast and
    reserved ranges report is_global True, so they are excluded separately.
    """
    if ip.is_loopback:
        return "loopback address"
    if ip.is_link_local:
        return "link-local address (cloud metadata range)"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_reserved:
        return "reserved address"
    if ip.is_private:
        return "private address"
    if not ip.is_global:
        return "non-routable address"
    return None


def check_ip(value: str) -> str | None:
    """Reason to reject a literal address, or None. Unparseable input is rejected."""
    try:
        return _reject_reason(ipaddress.ip_address(value))
    except ValueError:
        return "unparseable address"


def check_url_shape(url: str, *, allow_private: bool = False) -> str | None:
    """Scheme/host validation that needs no DNS. Returns a reason or None."""
    if not isinstance(url, str) or not url.strip():
        return "empty URL"
    try:
        parsed = urlparse(url)
        port = parsed.port
        host = (parsed.hostname or "").strip().lower().rstrip(".")
    except ValueError:
        return "unparseable URL"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return f"unsupported scheme '{parsed.scheme}'"

    if port is not None and not 0 < port <= 65535:
        return "invalid port"
    if not host:
        return "URL has no host"
    if host in BLOCKED_HOSTNAMES:
        return f"blocked hostname '{host}'"
    if host.endswith((".localhost", ".internal", ".local")):
        return f"blocked internal hostname '{host}'"

    # A bare IP in the URL needs no resolution.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return None if allow_private else check_ip(host)


async def resolve_all(host: str, port: int) -> list[str]:
    """Every address `host` resolves to. Raises on resolution failure."""
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
        timeout=DNS_TIMEOUT,
    )
    return [info[4][0] for info in infos]


async def check_url(url: str, *, allow_private: bool = False) -> str | None:
    """Full check: shape, then DNS. Returns a rejection reason, or None if allowed.

    `allow_private=True` skips address validation entirely, for deployments that
    intentionally stream from a LAN media server. Scheme and hostname blocking
    still apply.
    """
    shape_problem = check_url_shape(url, allow_private=allow_private)
    if shape_problem:
        return shape_problem

    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        return None  # a literal address was already validated by check_url_shape
    except ValueError:
        # Not an IP literal, so it is a name that needs resolving. This is the
        # normal path for every hostname URL, not a swallowed failure -- hence no
        # log line here.
        pass

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        await public_addresses(host, port, allow_private=allow_private)
    except asyncio.TimeoutError:
        return f"DNS lookup for '{host}' timed out"
    except Exception as e:
        return f"DNS lookup for '{host}' failed: {e}"

    return None


async def public_addresses(host: str, port: int, *, allow_private: bool = False) -> list[str]:
    """Resolve once, reject mixed public/private answers, return IPs to connect to."""
    literal_host = f"[{host}]" if ":" in host else host
    reason = check_url_shape(f"http://{literal_host}:{port}/", allow_private=allow_private)
    if reason:
        raise ValueError(reason)
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = await resolve_all(host, port)
    if not addresses:
        raise ValueError(f"'{host}' did not resolve")
    for address in addresses:
        reason = check_ip(address)
        if reason and not allow_private:
            raise ValueError(f"'{host}' resolves to a {reason}")
    return list(dict.fromkeys(addresses))


async def is_url_allowed(url: str, *, allow_private: bool = False) -> bool:
    """Boolean form of check_url, with the rejection logged."""
    reason = await check_url(url, allow_private=allow_private)
    if reason:
        logger.warning(f"[url_guard] Blocked URL: {reason} — {str(url)[:120]}")
        return False
    return True
