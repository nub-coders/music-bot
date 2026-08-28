"""Tests for url_guard -- the SSRF gate on user-supplied /play URLs.

Anyone in a group can pass a URL to /play, so the bot must refuse to fetch
loopback, private, link-local (cloud metadata) and other non-routable targets.
"""
import asyncio

import pytest

import url_guard


# ── literal addresses ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("addr,fragment", [
    ("127.0.0.1", "loopback"),
    ("127.1.2.3", "loopback"),
    ("10.0.0.1", "private"),
    ("172.16.5.4", "private"),
    ("192.168.1.1", "private"),
    ("169.254.169.254", "link-local"),   # AWS/GCP/Azure metadata
    ("100.64.0.1", "non-routable"),      # carrier-grade NAT
    ("0.0.0.0", "private"),
    ("224.0.0.1", "multicast"),
    ("::1", "loopback"),
    ("fc00::1", "private"),
    ("fe80::1", "link-local"),
    ("::ffff:127.0.0.1", "loopback"),        # IPv4-mapped loopback
    ("::ffff:169.254.169.254", "link-local"),
    ("2002:7f00:0001::", "private"),         # 6to4 wrapping 127.0.0.1
    ("64:ff9b::7f00:1", "reserved"),         # NAT64 wrapping 127.0.0.1
])
def test_non_routable_literals_are_rejected(addr, fragment):
    reason = url_guard.check_ip(addr)
    assert reason is not None, f"{addr} should be rejected"
    assert fragment in reason


@pytest.mark.parametrize("addr", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2001:4860:4860::8888"])
def test_public_literals_are_allowed(addr):
    assert url_guard.check_ip(addr) is None


def test_garbage_address_is_rejected():
    assert url_guard.check_ip("not-an-ip") == "unparseable address"


# ── URL shape ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,fragment", [
    ("file:///etc/passwd", "scheme"),
    ("gopher://example.com/", "scheme"),
    ("ftp://example.com/song.mp3", "scheme"),
    ("", "empty"),
    ("   ", "empty"),
    ("http://", "no host"),
    ("http://localhost:8080/admin", "localhost"),
    ("http://LOCALHOST/admin", "localhost"),
    ("http://localhost./admin", "localhost"),
    ("http://metadata.google.internal/computeMetadata/v1/", "metadata.google.internal"),
    ("http://instance-data/latest/meta-data/", "instance-data"),
    ("http://nas.local/media.mp3", "internal hostname"),
    ("http://svc.internal/media.mp3", "internal hostname"),
    ("http://169.254.169.254/latest/meta-data/", "link-local"),
    ("http://127.0.0.1:6379/", "loopback"),
    ("http://[::1]:8080/", "loopback"),
])
def test_bad_url_shapes_are_rejected(url, fragment):
    reason = url_guard.check_url_shape(url)
    assert reason is not None, f"{url} should be rejected"
    assert fragment in reason


@pytest.mark.parametrize("url", [
    "https://example.com/song.mp3",
    "http://8.8.8.8/stream.m3u8",
    "https://cdn.example.org:8443/a/b.mp4",
])
def test_good_url_shapes_pass_the_dns_free_check(url):
    assert url_guard.check_url_shape(url) is None


def test_non_string_input_is_rejected():
    assert url_guard.check_url_shape(None) == "empty URL"
    assert url_guard.check_url_shape(12345) == "empty URL"


# ── full check, with DNS stubbed ──────────────────────────────────────────────

@pytest.fixture
def resolver(monkeypatch):
    """Replace DNS with a controllable mapping."""
    mapping = {}

    async def _fake_resolve(host, port):
        if host not in mapping:
            raise OSError(f"Name or service not known: {host}")
        result = mapping[host]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(url_guard, "resolve_all", _fake_resolve)
    return mapping


async def test_public_name_is_allowed(resolver):
    resolver["example.com"] = ["93.184.216.34"]
    assert await url_guard.check_url("https://example.com/song.mp3") is None


async def test_dns_rebinding_to_loopback_is_rejected(resolver):
    """A perfectly ordinary hostname pointed at 127.0.0.1 must not slip through
    the shape check -- this is why resolution happens at all."""
    resolver["evil.example.com"] = ["127.0.0.1"]

    reason = await url_guard.check_url("https://evil.example.com/song.mp3")

    assert reason is not None
    assert "127.0.0.1" in reason
    assert "loopback" in reason


async def test_dns_pointing_at_metadata_is_rejected(resolver):
    resolver["meta.example.com"] = ["169.254.169.254"]
    reason = await url_guard.check_url("http://meta.example.com/latest/meta-data/")
    assert "link-local" in reason


async def test_any_bad_address_in_the_set_rejects(resolver):
    """Round-robin DNS returning one public and one private address must fail
    closed: the connect could pick either."""
    resolver["mixed.example.com"] = ["93.184.216.34", "10.1.2.3"]

    reason = await url_guard.check_url("https://mixed.example.com/song.mp3")

    assert reason is not None
    assert "10.1.2.3" in reason


async def test_unresolvable_host_is_rejected(resolver):
    reason = await url_guard.check_url("https://nope.example.com/song.mp3")
    assert "failed" in reason


async def test_empty_resolution_is_rejected(resolver):
    resolver["void.example.com"] = []
    reason = await url_guard.check_url("https://void.example.com/song.mp3")
    assert "did not resolve" in reason


async def test_dns_timeout_is_rejected(resolver):
    resolver["slow.example.com"] = asyncio.TimeoutError()
    reason = await url_guard.check_url("https://slow.example.com/song.mp3")
    assert "timed out" in reason


async def test_literal_public_ip_skips_dns(resolver):
    """No resolver entry is needed; a literal address is validated directly."""
    assert await url_guard.check_url("https://8.8.8.8/stream.m3u8") is None


async def test_literal_private_ip_is_rejected_without_dns(resolver):
    reason = await url_guard.check_url("http://192.168.1.10:8096/stream.mp3")
    assert "private" in reason


# ── the allow_private escape hatch ────────────────────────────────────────────

async def test_allow_private_permits_lan_addresses(resolver):
    assert await url_guard.check_url(
        "http://192.168.1.10:8096/stream.mp3", allow_private=True
    ) is None


async def test_allow_private_still_blocks_bad_schemes(resolver):
    reason = await url_guard.check_url("file:///etc/passwd", allow_private=True)
    assert "scheme" in reason


async def test_allow_private_still_blocks_metadata_hostnames(resolver):
    reason = await url_guard.check_url(
        "http://metadata.google.internal/computeMetadata/v1/", allow_private=True
    )
    assert reason is not None


# ── is_url_allowed wrapper ────────────────────────────────────────────────────

async def test_is_url_allowed_logs_and_returns_false(resolver, caplog):
    resolver["evil.example.com"] = ["127.0.0.1"]

    with caplog.at_level("WARNING"):
        allowed = await url_guard.is_url_allowed("https://evil.example.com/x.mp3")

    assert allowed is False
    assert any("Blocked URL" in r.message for r in caplog.records)


async def test_is_url_allowed_true_for_public(resolver):
    resolver["example.com"] = ["93.184.216.34"]
    assert await url_guard.is_url_allowed("https://example.com/song.mp3") is True
