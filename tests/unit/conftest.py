"""Unit tests must never use the network (Story 9.1, AC 4).

Every unit test runs with outside connections watched. An attempt does not raise inside the code
under test, because much of Finnie handles network errors on purpose (fallbacks) and would hide it.
Instead the attempt is recorded, behaves like a refused connection, and the test fails afterwards.
Loopback addresses are allowed. Tests that need the real embedding model live in tests/integration.
"""

import ipaddress
import socket

import pytest


def _is_local(host) -> bool:
    if host in ("localhost", None, ""):
        return True
    if isinstance(host, (bytes, str)) and str(host).startswith("/"):
        return True  # a Unix socket path
    try:
        return ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def network_attempts(monkeypatch):
    """The list of outside connections this test tried to make. Clear it if the test does so on purpose."""
    attempts: list[str] = []
    real_connect, real_connect_ex, real_getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def connect(self, address):
        if isinstance(address, tuple) and not _is_local(address[0]):
            attempts.append(f"connect {address[0]}:{address[1]}")
            raise ConnectionRefusedError("network is not available in unit tests")
        return real_connect(self, address)

    def connect_ex(self, address):
        if isinstance(address, tuple) and not _is_local(address[0]):
            attempts.append(f"connect {address[0]}:{address[1]}")
            return 111  # ECONNREFUSED
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local(host):
            attempts.append(f"lookup {host}")
            raise socket.gaierror("network is not available in unit tests")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield attempts
    assert not attempts, f"this unit test tried to use the network: {attempts}"
