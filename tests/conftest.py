"""Collection-safe defaults: no local secrets, live database, or network calls.

Apply these patches before test modules import application modules. Individual
tests should mock the external boundary they exercise; ``allow_localhost`` is
available for tests that deliberately start a local HTTP server.
"""

import ipaddress
import socket

import dotenv
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient


_isolation = pytest.MonkeyPatch()
_isolation.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

for _name in (
    "BOT_TOKEN",
    "STRING_SESSION",
    "STRING_SESSION1",
    "STRING_SESSION2",
    "STRING_SESSION3",
    "STRING_SESSION4",
    "STRING_SESSION5",
    "YOUTUBE_API_KEYS",
    "YTUBE_API_TOKEN",
    "YT_API_TOKEN",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "YT_COOKIES_FILE",
    "COOKIES_FROM_BROWSER",
    "INITIAL_ADMIN_IDS",
    "LOGGER_ID",
):
    _isolation.setenv(_name, "")

for _name, _value in {
    "MONGODB_URI": "mongodb://localhost:27017",
    "DB_NAME": "musicbot_test",
    "OWNER_ID": "123456789",
    "API_ID": "12345",
    "API_HASH": "0" * 32,
    "YTUBE_API_BASE_URL": "https://provider.invalid",
    "NUB_YT_API_BASE_URL": "https://provider.invalid",
    "COOKIES_BOOTSTRAP_URL": "https://provider.invalid",
    "COOKIES_REFRESH_HOURS": "0",
    "ALLOW_PRIVATE_STREAM_URLS": "False",
}.items():
    _isolation.setenv(_name, _value)


_motor_init = AsyncIOMotorClient.__init__


def _offline_motor_init(self, *args, **kwargs):
    kwargs["connect"] = False
    _motor_init(self, *args, **kwargs)


def _blocked_mongo(*args, **kwargs):
    raise AssertionError("Live MongoDB access is disabled in tests; mock the collection operation.")


_isolation.setattr(AsyncIOMotorClient, "__init__", _offline_motor_init)
_isolation.setattr(MongoClient, "_get_topology", _blocked_mongo)

_socket_connect = socket.socket.connect
_socket_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo


def _blocked_connect(sock, address):
    if sock.family == socket.AF_UNIX:
        return _socket_connect(sock, address)
    raise AssertionError("Network access is disabled in tests; mock the request or use allow_localhost.")


def _blocked_connect_ex(sock, address):
    if sock.family == socket.AF_UNIX:
        return _socket_connect_ex(sock, address)
    raise AssertionError("Network access is disabled in tests; mock the request or use allow_localhost.")


def _blocked_getaddrinfo(*args, **kwargs):
    raise AssertionError("DNS access is disabled in tests; mock socket.getaddrinfo.")


_isolation.setattr(socket.socket, "connect", _blocked_connect)
_isolation.setattr(socket.socket, "connect_ex", _blocked_connect_ex)
_isolation.setattr(socket, "getaddrinfo", _blocked_getaddrinfo)


def _is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture
def allow_localhost(monkeypatch):
    """Permit only loopback network connections for local HTTP test servers."""
    def connect(sock, address):
        if sock.family == socket.AF_UNIX or _is_loopback(address[0]):
            return _socket_connect(sock, address)
        return _blocked_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family == socket.AF_UNIX or _is_loopback(address[0]):
            return _socket_connect_ex(sock, address)
        return _blocked_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        if _is_loopback(host):
            return _getaddrinfo(host, *args, **kwargs)
        return _blocked_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


def pytest_unconfigure(config):
    _isolation.undo()
